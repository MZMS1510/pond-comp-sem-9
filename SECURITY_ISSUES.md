# Vulnerabilidades de Segurança no Projeto de Servidor Web ESP32

Este documento descreve as vulnerabilidades de segurança encontradas no projeto de servidor web ESP32.

## 1. Credenciais WiFi Codificadas (Hardcoded)

**Vulnerabilidade:** O SSID e a senha da rede WiFi estão codificados diretamente no arquivo `src/main.cpp`.

**Arquivo:** `src/main.cpp`
**Linhas:**
```cpp
const char* ssid = "Inteli.Iot";
const char* password = "%(Yk(sxGMtvFEs.3";
```

**Risco:** Armazenar credenciais no código-fonte é altamente inseguro. Se o código for compartilhado, publicado em um sistema de controle de versão ou se o firmware do dispositivo for lido, essas credenciais serão expostas, concedendo acesso não autorizado à rede WiFi.

**Mitigação:**

- Use um método de provisionamento para definir credenciais em tempo de execução, como WiFiManager, SmartConfig ou um arquivo de configuração armazenado em SPIFFS/LittleFS.
- Armazene credenciais em um arquivo de configuração separado e não rastreado (por exemplo, `config.h`) que é incluído pelo arquivo de origem principal, mas excluído do controle de versão usando `.gitignore`.
- Use variáveis de ambiente se o sistema de compilação as suportar.

## 2. Falta de Autenticação e Autorização

**Vulnerabilidade:** O servidor web não implementa nenhuma forma de autenticação ou autorização. Qualquer pessoa conectada à mesma rede WiFi pode enviar solicitações HTTP para controlar os pinos GPIO.

**Arquivo:** `src/main.cpp` (dentro da função `loop()`)

**Risco:** Isso permite que qualquer usuário (ou ator mal-intencionado) na rede controle livremente o hardware conectado aos pinos GPIO. Isso pode levar a danos físicos, interrupção do serviço ou outras consequências não intencionais.

**Mitigação:**

- Implemente um sistema de login com nome de usuário e senha.
- Use chaves de API ou tokens de acesso que devem ser incluídos nos cabeçalhos da solicitação HTTP.
- Restrinja o acesso a uma lista específica de endereços IP ou MAC.

## 3. Comunicação Insegura (HTTP)

**Vulnerabilidade:** O servidor usa HTTP simples para toda a comunicação. Todos os dados são transmitidos em texto não criptografado (cleartext).

**Arquivo:** `src/main.cpp`
**Linha:** `WiFiServer server(80);`

**Risco:** Um invasor na mesma rede pode realizar um ataque Man-in-the-Middle (MitM) para interceptar, ler ou modificar o tráfego entre o cliente e o ESP32. Isso é especialmente perigoso se a autenticação for adicionada, pois as credenciais seriam enviadas em texto não criptografado.

**Mitigação:**

- Implemente HTTPS para criptografar toda a comunicação. A classe `WiFiClientSecure` pode ser usada junto com um certificado SSL/TLS autoassinado ou emitido por CA.

## 4. Vulnerabilidade de Negação de Serviço (DoS)

**Vulnerabilidade:** A variável global `header`, que é um objeto `String`, concatena continuamente os dados recebidos do cliente sem um limite de tamanho.

**Arquivo:** `src/main.cpp`
**Linha:** `header += c;`

**Risco:** Um cliente mal-intencionado pode enviar uma solicitação HTTP muito grande, fazendo com que a string `header` cresça indefinidamente. Isso esgotará rapidamente a RAM limitada no ESP32, levando a uma falha do sistema e reinicialização (Negação de Serviço).

**Mitigação:**

- Imponha um limite de tamanho razoável na solicitação HTTP recebida.
- Leia a solicitação linha por linha e analise-a em tempo real, em vez de acumular toda a solicitação em uma única string grande. Descarte quaisquer dados que excedam o tamanho máximo permitido do cabeçalho.
- Use arrays de caracteres (`char[]`) com um tamanho fixo em vez da classe `String` para melhor gerenciamento de memória e para evitar fragmentação de heap.

## 5. Falsificação de Solicitação entre Sites (CSRF)

**Vulnerabilidade:** As operações de mudança de estado (ligar/desligar GPIOs) são acionadas por solicitações HTTP `GET` simples.

**Arquivo:** `src/main.cpp` (dentro da função `loop()`)

**Risco:** Um invasor pode criar uma página da web, e-mail ou link malicioso que envia uma solicitação para o endereço IP do ESP32. Se um usuário na mesma rede local interagir com esse conteúdo malicioso (por exemplo, visitando uma página da web), seu navegador enviará automaticamente a solicitação para o ESP32, alterando o estado do GPIO sem seu conhecimento ou consentimento. Por exemplo, um invasor pode incorporar `<img src="http://<ESP32_IP>/26/on">` em uma postagem de fórum.

**Mitigação:**

- Use solicitações HTTP `POST` para quaisquer ações de mudança de estado em vez de `GET`.
- Implemente um mecanismo de token anti-CSRF. O servidor deve gerar um token único e aleatório para cada sessão ou solicitação e exigir que ele seja incluído em solicitações `POST` subsequentes.

## 6. Controle Direto de LEDs via URL (endpoints previsíveis)

**Vulnerabilidade:**  
O firmware permite alterar o estado dos LEDs/GPIOs diretamente por meio de URLs previsíveis (por exemplo: `http://<ESP32_IP>/26/on` e `http://<ESP32_IP>/26/off`). Isso significa que qualquer cliente capaz de alcançar o servidor pode manipular o hardware apenas acessando links específicos.

**Arquivo:** `src/main.cpp`  
**Local:** Lógica de análise da requisição HTTP dentro da função `loop()`.

**Risco:**  
- Endpoints simples e totalmente previsíveis permitem que qualquer usuário da rede (ou um invasor) controle facilmente os GPIOs.  
- Scanners automatizados podem detectar esses padrões e manipular o dispositivo sem autorização.  
- Combina-se com outras vulnerabilidades (como ausência de autenticação e CSRF), facilitando ataques remotos sem interação do usuário.  
- Se o número do pino é utilizado diretamente da URL sem validação, entradas maliciosas podem causar comportamentos inesperados.

**Mitigação:**  
- Remover o controle direto via `GET` público e migrar para uma API baseada em `POST` autenticada.  
- Exigir autenticação (senha, token, API key ou sessão).  
- Validar estritamente qualquer valor extraído da URL e permitir apenas pinos pré-configurados.  
- Implementar rate-limiting e registro de tentativas de acesso.  
- Utilizar HTTPS/TLS para proteger o tráfego e evitar vazamento de comandos.  
