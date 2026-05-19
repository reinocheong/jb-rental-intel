const { default: makeWASocket, useMultiFileAuthState } = require("@whiskeysockets/baileys");
const http = require('http');
const { handleIncomingMessage } = require('./lib/message_router');

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState('wa_session');
  const sock = makeWASocket({ auth: state, printQRInTerminal: true });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('messages.upsert', m => handleIncomingMessage(sock, m));

  http.createServer((req, res) => {
    if (req.url.startsWith('/send')) {
      // Logic to parse params and sock.sendMessage
      res.end('ok');
    }
  }).listen(3456);
  console.log('[wa/wa_daemon.js] 服务运行在 3456');
}

startSock();
