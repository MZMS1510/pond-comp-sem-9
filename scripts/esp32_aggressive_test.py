#!/usr/bin/env python3
"""
ESP32 Aggressive Security Testing
Teste intensivo: 1000 req/s por 1 minuto + múltiplas portas
"""

import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

TARGET_IP = "http://10.128.0.201"
TIMEOUT = 3
TOTAL_REQUESTS = 60000  # 60 segundos x 1000 req/s
REQUEST_RATE = 1000  # requisições por segundo
PORTS_TO_TEST = [26, 27]
TEST_PORTS = [26, 27]  # Portas para alternar

class AggressiveTester:
    def __init__(self, target_url):
        self.target_url = target_url
        self.lock = threading.Lock()
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'timeout': 0,
            'connection_error': 0,
            'other_error': 0,
            'start_time': None,
            'end_time': None,
            'responses': {},
            'errors': []
        }
    
    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
    
    def make_request(self, port, request_num=0):
        """Faz uma requisição individual alternando on/off"""
        try:
            command = 'on' if request_num % 3 == 0 else 'off'
            url = f"{self.target_url}/{port}/{command}"
            response = requests.get(url, timeout=TIMEOUT)
            
            with self.lock:
                self.stats['total'] += 1
                status_code = response.status_code
                
                if status_code not in self.stats['responses']:
                    self.stats['responses'][status_code] = 0
                self.stats['responses'][status_code] += 1
                
                if status_code < 500:
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1
            
            return True
        
        except requests.exceptions.Timeout:
            with self.lock:
                self.stats['total'] += 1
                self.stats['timeout'] += 1
            return False
        
        except requests.exceptions.ConnectionError as e:
            with self.lock:
                self.stats['total'] += 1
                self.stats['connection_error'] += 1
                self.stats['errors'].append(f"Connection Error: {str(e)[:50]}")
            return False
        
        except Exception as e:
            with self.lock:
                self.stats['total'] += 1
                self.stats['other_error'] += 1
                self.stats['errors'].append(str(e)[:50])
            return False
    
    def flood_port(self, port, duration=60, rate=1000):
        """Flood alternando entre portas e comandos"""
        self.log(f"🔥 Iniciando flood: alternando portas 26↔27 e comandos on↔off, {TOTAL_REQUESTS} requisições")
        self.stats['start_time'] = time.time()
        
        start = time.time()
        request_count = 0
        last_log = time.time()
        
        try:
            # Muito mais workers para manter alta taxa
            max_workers = 1000
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                while request_count < TOTAL_REQUESTS:
                    # Limpar futures completadas continuamente
                    new_futures = []
                    for f in futures:
                        if not f.done():
                            new_futures.append(f)
                        else:
                            try:
                                f.result(timeout=0.001)
                            except:
                                pass
                    
                    futures = new_futures
                    
                    # Manter fila cheia de requisições
                    target_futures = 500  # Muito mais na fila
                    while len(futures) < target_futures and request_count < TOTAL_REQUESTS:
                        try:
                            # Alternar entre portas a cada requisição
                            current_port = TEST_PORTS[request_count % len(TEST_PORTS)]
                            future = executor.submit(self.make_request, current_port, request_count)
                            futures.append(future)
                            request_count += 1
                        except Exception as e:
                            self.log(f"Erro ao submeter: {e}")
                            break
                    
                    # Log a cada 10 segundos
                    now = time.time()
                    if now - last_log >= 10:
                        elapsed = now - start
                        actual_rate = request_count / elapsed if elapsed > 0 else 0
                        remaining = TOTAL_REQUESTS - request_count
                        self.log(f"  ⏱️  {elapsed:.1f}s: {request_count}/{TOTAL_REQUESTS} reqs ({actual_rate:.0f} req/s) | "
                                f"Faltam: {remaining} | Sucesso: {self.stats['success']}, Erros: {self.stats['connection_error']}")
                        last_log = now
                    
                    time.sleep(0.0001)  # Delay bem pequeno
                
                # Aguardar restantes
                self.log(f"  Finalizando {len(futures)} requisições pendentes...")
                for f in futures:
                    try:
                        f.result(timeout=0.5)
                    except:
                        pass
        
        except Exception as e:
            self.log(f"❌ Erro durante flood: {e}")
        
        self.stats['end_time'] = time.time()
    
    def print_report(self):
        """Relatório detalhado"""
        elapsed = (self.stats['end_time'] - self.stats['start_time']) if self.stats['end_time'] else 0
        
        print("\n" + "="*70)
        print("📊 RELATÓRIO DO FLOOD")
        print("="*70)
        print(f"Duração: {elapsed:.2f}s")
        print(f"Total de requisições: {self.stats['total']}")
        print(f"Taxa média: {self.stats['total']/elapsed:.2f} req/s" if elapsed > 0 else "N/A")
        print(f"\n✅ Sucesso: {self.stats['success']} ({100*self.stats['success']/max(1, self.stats['total']):.1f}%)")
        print(f"❌ Falhas: {self.stats['failed']}")
        print(f"⏱️  Timeouts: {self.stats['timeout']}")
        print(f"🔌 Conexão recusada: {self.stats['connection_error']}")
        print(f"⚠️  Outros erros: {self.stats['other_error']}")
        
        print(f"\n📈 Códigos HTTP:")
        for code in sorted(self.stats['responses'].keys()):
            count = self.stats['responses'][code]
            pct = 100 * count / max(1, self.stats['total'])
            print(f"  {code}: {count} ({pct:.1f}%)")
        
        if self.stats['errors']:
            print(f"\n⚠️  Últimos 5 erros únicos:")
            unique_errors = list(set(self.stats['errors']))[:5]
            for error in unique_errors:
                print(f"  - {error}")
        
        print("="*70 + "\n")

def test_porta_individual(port):
    """Testa alternando entre portas"""
    tester = AggressiveTester(TARGET_IP)
    
    print(f"\n{'🎯'*35}")
    print(f"TESTE AGRESSIVO")
    print(f"{'🎯'*35}")
    
    tester.flood_port(port, duration=60, rate=REQUEST_RATE)
    tester.print_report()
    
    return tester.stats

def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║   ESP32 AGGRESSIVE DoS TEST - 60.000 REQUISIÇÕES (1K/s)       ║
    ║   Alternando: Portas 26↔27 + Comandos on↔off                  ║
    ║                                                                ║
    ║  ⚠️  CUIDADO: Este teste é MUITO agressivo!                   ║
    ║     Use apenas em dispositivos que você controla             ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    all_results = {}
    
    try:
        for port in PORTS_TO_TEST:
            results = test_porta_individual(port)
            all_results[port] = results
            time.sleep(2)  # Delay entre portas
        
        # Relatório comparativo
        print("\n" + "="*70)
        print("📊 COMPARAÇÃO ENTRE PORTAS")
        print("="*70)
        
        for port in PORTS_TO_TEST:
            stats = all_results[port]
            taxa_sucesso = 100 * stats['success'] / max(1, stats['total'])
            print(f"\nPorta {port}:")
            print(f"  Requisições: {stats['total']}")
            print(f"  Taxa de sucesso: {taxa_sucesso:.1f}%")
            print(f"  Conexões recusadas: {stats['connection_error']}")
            if stats['connection_error'] > 0:
                print(f"  ⚠️  POSSÍVEL CRASH DETECTADO!")
        
        print("="*70 + "\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
