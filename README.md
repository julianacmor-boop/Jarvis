# Jarvis

Painel de tablet em uma única página (`index.html`), feito para o Chrome no Android.

## O que faz

- Relógio, data, saudação e progresso do dia
- Clima de Guaratinguetá e Lorena (Open-Meteo), atualizado a cada 10 minutos
- Tarefas e timers, salvos no próprio aparelho
- Comandos de voz em português: "Falar" (um comando) e "Escuta" (diga "Jarvis" antes do comando)
- Respostas em voz alta, com escolha de voz, tom e velocidade
- Saudações: "bom dia", "boa tarde", "boa noite"
- Agenda do Google dos próximos 7 dias, com lembretes por voz (arquivo criptografado, abre com senha)
- Atalhos que abrem direto no app do Android: Gmail, Agenda, YouTube, YouTube Music, Mapas, WhatsApp e Spotify
- Atalhos do NAV Aluno (atividades, notas, aulas e mensagens)
- Confere sozinho se há versão nova e recarrega

## Exemplos de comandos

- "abrir YouTube", "abrir música", "abrir agenda", "abrir atividades"
- "timer de 10 minutos"
- "adicionar tarefa comprar pão", "concluir tarefa pão"
- "como está o tempo em Lorena?", "previsão para amanhã"
- "o que tenho hoje", "o que tenho amanhã", "agenda da semana"
- "ajuda" lista tudo

## Publicação

GitHub Pages: Settings > Pages > Deploy from a branch > main > / (root).
O microfone só funciona em https.

## Agenda

A agenda fica em `agenda.enc.json`, criptografada (AES-GCM, chave derivada da senha com PBKDF2). O repositório é público, mas só quem tem a senha lê os compromissos. A senha nunca fica no repositório.
O arquivo é atualizado automaticamente 3 vezes ao dia (05h, 11h e 17h, horário de Brasília) pelo GitHub Actions, em `.github/workflows/agenda.yml`, usando `scripts/update_agenda.py`.
O painel mostra a data da última atualização.

### Configuração (uma vez)

1. No Google Agenda (versão para computador): Configurações > clique no seu calendário > Integrar agenda > copie o **Endereço secreto no formato iCal**.
2. No GitHub: Settings > Secrets and variables > Actions > New repository secret:
   - `ICAL_URL`: o endereço copiado (vários calendários: separe por espaço)
   - `AGENDA_PASS`: a senha da agenda, a mesma digitada no painel
3. Aba Actions > Atualizar agenda > Run workflow, para testar.

O endereço secreto dá acesso de leitura à agenda: nunca o coloque em arquivos do repositório.
Os lembretes tocam e falam só enquanto o painel está aberto.

## Limites

- O painel não lê o Gmail nem o NAV, só abre os apps e sites. A Agenda vem do arquivo criptografado, atualizado sob pedido.
- O Chrome só deixa abrir outro app logo depois de um toque. Por voz, se não abrir sozinho, toque no botão **Abrir** que aparece na conversa.
- Os atalhos de app dependem do app estar instalado. Sem o app, abre o site.

## Notícias do dia

O quadro "Notícias do dia" lê `news.json` (público, sem criptografia). Comandos de voz: "notícias do dia", "notícias do Brasil", "notícias do mundo", "manchetes".
Fontes: Agência Brasil, CNN Brasil e Euronews (Globo e UOL bloqueiam a leitura automática). Para renovar, peça no Claude "atualiza as notícias".
