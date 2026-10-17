# Jarvis

Painel de tablet em uma única página (`index.html`), feito para o Chrome no Android.

## O que faz

- Relógio, data, saudação e progresso do dia
- Clima de Guaratinguetá e Lorena (Open-Meteo), atualizado a cada 10 minutos
- Tarefas e timers, salvos no próprio aparelho
- Comandos de voz em português: "Falar" (um comando) e "Escuta" (diga "Jarvis" antes do comando)
- Respostas em voz alta, com escolha de voz, tom e velocidade
- Saudações: "bom dia", "boa tarde", "boa noite"
- Atalhos que abrem direto no app do Android: Gmail, Agenda, YouTube, YouTube Music, Mapas, WhatsApp e Spotify
- Atalhos do NAV Aluno (atividades, notas, aulas e mensagens)
- Confere sozinho se há versão nova e recarrega

## Exemplos de comandos

- "abrir YouTube", "abrir música", "abrir agenda", "abrir atividades"
- "timer de 10 minutos"
- "adicionar tarefa comprar pão", "concluir tarefa pão"
- "como está o tempo em Lorena?", "previsão para amanhã"
- "ajuda" lista tudo

## Publicação

GitHub Pages: Settings > Pages > Deploy from a branch > main > / (root).
O microfone só funciona em https.

## Limites

- O painel não lê o conteúdo do Gmail, da Agenda nem do NAV. Ele só abre os apps e sites.
- O Chrome só deixa abrir outro app logo depois de um toque. Por voz, se não abrir sozinho, toque no botão **Abrir** que aparece na conversa.
- Os atalhos de app dependem do app estar instalado. Sem o app, abre o site.
