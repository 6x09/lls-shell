LLS - Linux Law Socket (Reverse Shell Generator)
A powerful command-line tool for generating reverse shell payloads with strong encoding options designed for legitimate cybersecurity testing and penetration testing purposes.

Features
13 Advanced Encoders: Multiple encoding options for AV evasion

none, xor, multixor, base64, rot13, caesar, polymorphic, stealth, sgn, alltheway, dynamicxor, hex, unicode
Multi-Platform Support

Linux (TCP, UDP, Bind)
Windows (TCP, UDP)
BSD
Multiple Payload Types

bash, python, perl, php, ruby, netcat, socat
PowerShell multiple methods
Output Formats

hex, c, python, powershell, bash, raw, url
Built-in Listener: Start listeners and manage reverse shells

Payload Verification: Entropy analysis and payload validation

Installation
cd C:\Users\Administrator\Desktop\LLS
py LLS.py
Or create a batch file:

@echo off
py LLS.py
pause
Usage
Interactive Mode
Run the tool and use commands:

py LLS.py
Available Commands
gen <platform> <type> <host> <port> [encoder] [key]
    platform : linux, windows, bsd
    type     : tcp, udp, bind
    encoder  : none, xor, multixor, base64, rot13, caesar, polymorphic,
               stealth, sgn, alltheway, dynamicxor, hex, unicode

encoders    - Show all available encoders
verify      - Verify current payload
out <format> - Output format: hex, c, python, powershell, bash, raw, url
save <file> - Save payload to file
copy        - Copy payload to clipboard
listen <host> <port> - Start listener
shells      - Show connected shells
info        - Show payload info
clear       - Clear screen
help        - Show this help
exit        - Exit
Examples
Generate a Linux TCP reverse shell with stealth encoding:

gen linux tcp 192.168.1.100 4444 stealth
Generate a Windows TCP reverse shell with XOR encoding:

gen windows tcp 10.10.10.10 8080 xor mykey
Generate with alltheway encoder:

gen linux tcp 192.168.1.1 443 alltheway
View all encoders:

encoders
Verify payload:

verify
Output as hex:

out hex
Output as C shellcode:

out c
Output as Python:

out python
Save to file:

save payload.txt
Start a listener:

listen 192.168.1.100 4444
Show connected shells:

shells
Screenshots
Main Banner
Main Banner

Encoder Selection
Encoders

Payload Generation
Payload

Encoder Details
Encoder	Description
none	No encoding
xor	Dynamic XOR with key
multixor	Multi-layer XOR
base64	Base64 standard
rot13	ROT13 cipher
caesar	Caesar cipher
polymorphic	Polymorphic mutation
stealth	AV evasion
sgn	Shikata Ga Nai
alltheway	Full chain encoding
dynamicxor	Dynamic XOR feedback
hex	Hex encoding
unicode	Unicode encoding
Important Notice
This tool is intended for:

Authorized penetration testing
Security research
Educational purposes
Red team operations
Unauthorized access to computer systems is illegal. Use this tool only on systems you own or have explicit permission to test.

Requirements
Python 3.6+
Works on Windows PowerShell, Linux, and macOS
License
Created by DeadBeef (deadbeef.lol)

For educational and authorized testing purposes only.
