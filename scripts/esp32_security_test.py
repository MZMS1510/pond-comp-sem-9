#!/usr/bin/env python3
"""
ESP32 Security Testing Script
Teste de vulnerabilidades em dispositivo IoT
Para fins educacionais apenas - use apenas em dispositivos que você possui
"""

import requests
import threading
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

# Configurações
TARGET_IP = "http://10.128.0.201"
TIMEOUT = 5
NUM_THREADS = 10
MAX_PAYLOAD_SIZE = 10000

class ESP32SecurityTester:
    def __init__(self, target_url):
        self.target_url = target_url
        self.results = {
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'errors': []
        }
        self.lock = threading.Lock()
    
    def log(self, message, level="INFO"):
        """Log com timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def update_result(self, success=False, timeout=False, error=None):
        """Thread-safe result update"""
        with self.lock:
            if error:
                self.results['errors'].append(error)
            elif timeout:
                self.results['timeouts'] += 1
            elif success:
                self.results['successful'] += 1
            else:
                self.results['failed'] += 1
    
    def test_basic_requests(self, port=1, count=5):
        """Teste 1: Requisições básicas para verificar responsividade"""
        self.log(f"Iniciando teste básico (porta {port}, {count} requisições)...")
        
        for i in range(count):
            try:
                for command in ['on', 'off']:
                    url = f"{self.target_url}/{port}/{command}"
                    response = requests.get(url, timeout=TIMEOUT)
                    status = "✓" if response.status_code in [200, 404, 405] else "✗"
                    self.log(f"  {status} GET {url} - Status: {response.status_code}")
                    self.update_result(success=response.status_code < 500)
            except requests.exceptions.Timeout:
                self.log(f"  ✗ Timeout em GET {url}", "WARN")
                self.update_result(timeout=True)
            except Exception as e:
                self.log(f"  ✗ Erro: {str(e)}", "ERROR")
                self.update_result(error=str(e))
            time.sleep(0.1)
    
    def flood_requests(self, duration=10, port=1):
        """Teste 2: Flood de requisições (DoS)"""
        self.log(f"Iniciando flood de requisições por {duration}s (porta {port})...")
        start_time = time.time()
        request_count = [0]  # usar lista para evitar nonlocal
        success_count = [0]
        error_count = [0]
        
        def make_request():
            try:
                url = f"{self.target_url}/{port}/on"
                response = requests.get(url, timeout=TIMEOUT)
                with self.lock:
                    request_count[0] += 1
                    if response.status_code < 500:
                        success_count[0] += 1
                self.update_result(success=response.status_code < 500)
            except requests.exceptions.Timeout:
                with self.lock:
                    request_count[0] += 1
                    error_count[0] += 1
                self.update_result(timeout=True)
            except requests.exceptions.ConnectionError:
                with self.lock:
                    request_count[0] += 1
                    error_count[0] += 1
                self.update_result(error="Connection refused")
            except Exception as e:
                with self.lock:
                    request_count[0] += 1
                    error_count[0] += 1
                self.update_result(error=str(e)[:50])
        
        try:
            with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                futures = []
                submission_time = time.time()
                
                while time.time() - start_time < duration:
                    try:
                        future = executor.submit(make_request)
                        futures.append(future)
                        
                        # Limpar futures completadas
                        completed = [f for f in futures if f.done()]
                        futures = [f for f in futures if not f.done()]
                        
                    except Exception as e:
                        self.log(f"Erro ao submeter requisição: {str(e)[:50]}", "WARN")
                        time.sleep(0.1)
                
                # Aguardar restantes com timeout
                for future in futures:
                    try:
                        future.result(timeout=2)
                    except Exception:
                        pass
        
        except Exception as e:
            self.log(f"Erro no flood: {str(e)[:50]}", "ERROR")
        
        elapsed = time.time() - start_time
        rps = request_count[0] / elapsed if elapsed > 0 else 0
        self.log(f"Flood concluído: {request_count[0]} requisições em {elapsed:.2f}s ({rps:.2f} req/s)")
        self.log(f"  Sucesso: {success_count[0]}, Erros: {error_count[0]}")
    
    def test_payload_sizes(self, port=1):
        """Teste 3: Payloads grandes para testar limite de buffer"""
        self.log(f"Testando payloads grandes (porta {port})...")
        
        payload_sizes = [100, 500, 1000, 5000, 10000, 50000, 100000]
        
        for size in payload_sizes:
            try:
                # Criar payload grande como comando
                large_payload = 'a' * size
                url = f"{self.target_url}/{port}/{large_payload}"
                
                self.log(f"  Testando payload de {size} bytes...")
                response = requests.get(url, timeout=TIMEOUT)
                
                status = "✓" if response.status_code < 500 else "✗"
                self.log(f"    {status} Status: {response.status_code}, Tamanho resposta: {len(response.content)}")
                self.update_result(success=response.status_code < 500)
                
            except requests.exceptions.Timeout:
                self.log(f"    ✗ Timeout com {size} bytes", "WARN")
                self.update_result(timeout=True)
            except requests.exceptions.ConnectionError as e:
                self.log(f"    ✗ Conexão recusada com {size} bytes - Possível crash!", "WARN")
                self.update_result(error=f"Crash possível em {size} bytes")
            except Exception as e:
                self.log(f"    ✗ Erro: {str(e)}", "ERROR")
                self.update_result(error=str(e))
            
            time.sleep(0.5)
    
    def test_malformed_requests(self, port=1):
        """Teste 4: Requisições malformadas"""
        self.log(f"Testando requisições malformadas (porta {port})...")
        
        malformed_payloads = [
            "",                              # vazio
            "     ",                         # espaços
            "on\n\roff",                     # com quebras de linha
            "on;off",                        # caracteres especiais
            "on\x00off",                     # null bytes
            "../../../etc/passwd",           # path traversal
            "on' or '1'='1",                 # SQL injection attempt
            "{\"cmd\": \"on\"}",             # JSON
            "<script>alert(1)</script>",     # XSS attempt
            "on" * 1000,                     # repetição
        ]
        
        for payload in malformed_payloads:
            try:
                url = f"{self.target_url}/{port}/{payload}"
                response = requests.get(url, timeout=TIMEOUT)
                self.log(f"  Payload: {repr(payload[:30])} - Status: {response.status_code}")
                self.update_result(success=response.status_code < 500)
            except Exception as e:
                self.log(f"  Payload: {repr(payload[:30])} - Erro: {str(e)[:50]}")
                self.update_result(error=str(e))
            
            time.sleep(0.2)
    
    def test_rate_limiting(self, port=1, requests_per_second=50):
        """Teste 5: Teste de rate limiting"""
        self.log(f"Testando rate limiting ({requests_per_second} req/s)...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        def make_request():
            nonlocal successful, failed
            try:
                url = f"{self.target_url}/{port}/on"
                response = requests.get(url, timeout=TIMEOUT)
                if response.status_code < 500:
                    successful += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        with ThreadPoolExecutor(max_workers=requests_per_second) as executor:
            futures = []
            for i in range(requests_per_second):
                futures.append(executor.submit(make_request))
            
            for future in as_completed(futures):
                try:
                    future.result(timeout=TIMEOUT)
                except:
                    pass
        
        elapsed = time.time() - start_time
        self.log(f"Taxa de sucesso: {successful}/{requests_per_second} ({100*successful/requests_per_second:.1f}%)")
    
    def test_multiple_ports(self, num_ports=10):
        """Teste 6: Teste em múltiplas portas simultaneamente"""
        self.log(f"Testando múltiplas portas (1-{num_ports})...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for port in range(1, num_ports + 1):
                future = executor.submit(self.make_port_request, port)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log(f"Erro: {str(e)}", "ERROR")
    
    def make_port_request(self, port):
        """Auxiliar para teste de múltiplas portas"""
        try:
            url = f"{self.target_url}/{port}/on"
            response = requests.get(url, timeout=TIMEOUT)
            self.log(f"  Porta {port}: Status {response.status_code}")
            self.update_result(success=response.status_code < 500)
        except Exception as e:
            self.log(f"  Porta {port}: {str(e)[:50]}")
            self.update_result(error=str(e))
    
    def print_report(self):
        """Imprime relatório final"""
        print("\n" + "="*60)
        print("RELATÓRIO FINAL DE TESTES")
        print("="*60)
        print(f"Requisições bem-sucedidas: {self.results['successful']}")
        print(f"Requisições falhadas: {self.results['failed']}")
        print(f"Timeouts: {self.results['timeouts']}")
        print(f"Total de erros: {len(self.results['errors'])}")
        
        if self.results['errors']:
            print("\nErros detectados:")
            for error in set(self.results['errors'][:5]):  # Top 5 erros únicos
                print(f"  - {error}")
        
        print("="*60 + "\n")

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║       ESP32 Security Vulnerability Testing Tool         ║
    ║                                                          ║
    ║  ⚠️  USO EDUCACIONAL APENAS - Teste apenas seus         ║
    ║      próprios dispositivos                              ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    tester = ESP32SecurityTester(TARGET_IP)
    
    try:
        # Teste de conectividade básico
        print(f"Verificando conectividade com {TARGET_IP}...")
        tester.log("Iniciando bateria de testes de segurança")
        
        # Executar testes
        try:
            tester.test_basic_requests(port=26, count=3)
        except Exception as e:
            tester.log(f"Erro no teste básico: {e}", "ERROR")
        time.sleep(1)
        
        try:
            tester.test_payload_sizes(port=26)
        except Exception as e:
            tester.log(f"Erro no teste de payload: {e}", "ERROR")
        time.sleep(1)
        
        try:
            tester.test_malformed_requests(port=26)
        except Exception as e:
            tester.log(f"Erro no teste malformado: {e}", "ERROR")
        time.sleep(1)
        
        try:
            tester.test_rate_limiting(port=26, requests_per_second=20)
            tester.test_rate_limiting(port=27, requests_per_second=20)
        except Exception as e:
            tester.log(f"Erro no teste de rate limiting: {e}", "ERROR")
        time.sleep(1)
        
        try:
            tester.flood_requests(duration=5, port=1)
        except Exception as e:
            tester.log(f"Erro no flood: {e}", "ERROR")
        time.sleep(1)
        
        try:
            tester.test_multiple_ports(num_ports=5)
        except Exception as e:
            tester.log(f"Erro no teste múltiplas portas: {e}", "ERROR")
        
        # Relatório
        tester.print_report()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
        tester.print_report()
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
