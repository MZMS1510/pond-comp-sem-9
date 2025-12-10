# Security Vulnerabilities in the ESP32 Web Server Project

This document outlines the security vulnerabilities found in the ESP32 web server project.

## 1. Hardcoded WiFi Credentials

**Vulnerability:** The WiFi network SSID and password are hardcoded directly in the `src/main.cpp` file.

**File:** `src/main.cpp`
**Lines:**
```cpp
const char* ssid = "Inteli.Iot";
const char* password = "%(Yk(sxGMtvFEs.3";
```

**Risk:** Storing credentials in source code is highly insecure. If the code is shared, published to a version control system, or the device's firmware is read, these credentials will be exposed, granting unauthorized access to the WiFi network.

**Mitigation:**
- Use a provisioning method to set credentials at runtime, such as WiFiManager, SmartConfig, or a configuration file stored in SPIFFS/LittleFS.
- Store credentials in a separate, untracked configuration file (e.g., `config.h`) that is included by the main source file but excluded from version control using `.gitignore`.
- Use environment variables if the build system supports them.

## 2. Lack of Authentication and Authorization

**Vulnerability:** The web server does not implement any form of authentication or authorization. Anyone connected to the same WiFi network can send HTTP requests to control the GPIO pins.

**File:** `src/main.cpp` (within the `loop()` function)

**Risk:** This allows any user (or malicious actor) on the network to freely control the hardware connected to the GPIO pins. This could lead to physical damage, disruption of service, or other unintended consequences.

**Mitigation:**
- Implement a login system with a username and password.
- Use API keys or access tokens that must be included in the HTTP request headers.
- Restrict access to a specific list of IP or MAC addresses.

## 3. Insecure Communication (HTTP)

**Vulnerability:** The server uses plain HTTP for all communication. All data is transmitted in cleartext.

**File:** `src/main.cpp`
**Line:** `WiFiServer server(80);`

**Risk:** An attacker on the same network can perform a Man-in-the-Middle (MitM) attack to intercept, read, or modify the traffic between the client and the ESP32. This is especially dangerous if authentication is added, as credentials would be sent in cleartext.

**Mitigation:**
- Implement HTTPS to encrypt all communication. The `WiFiClientSecure` class can be used along with a self-signed or CA-issued SSL/TLS certificate.

## 4. Denial of Service (DoS) Vulnerability

**Vulnerability:** The global `header` variable, which is a `String` object, continuously concatenates incoming data from the client without a size limit.

**File:** `src/main.cpp`
**Line:** `header += c;`

**Risk:** A malicious client can send a very large HTTP request, causing the `header` string to grow indefinitely. This will quickly exhaust the limited RAM on the ESP32, leading to a system crash and reboot (Denial of Service).

**Mitigation:**
- Enforce a reasonable size limit on the incoming HTTP request.
- Read the request line by line and parse it on the fly, instead of accumulating the entire request in a single large string. Discard any data that exceeds the maximum allowed header size.
- Use character arrays (`char[]`) with a fixed size instead of the `String` class for better memory management and to prevent heap fragmentation.

## 5. Cross-Site Request Forgery (CSRF)

**Vulnerability:** State-changing operations (turning GPIOs on/off) are triggered by simple HTTP `GET` requests.

**File:** `src/main.cpp` (within the `loop()` function)

**Risk:** An attacker can craft a malicious web page, email, or link that sends a request to the ESP32's IP address. If a user on the same local network interacts with this malicious content (e.g., by visiting a web page), their browser will automatically send the request to the ESP32, changing the GPIO state without their knowledge or consent. For example, an attacker could embed `<img src="http://<ESP32_IP>/26/on">` in a forum post.

**Mitigation:**
- Use HTTP `POST` requests for any state-changing actions instead of `GET`.
- Implement an anti-CSRF token mechanism. The server should generate a unique, random token for each session or request and require it to be included in subsequent `POST` requests.
