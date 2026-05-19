const handleIncomingMessage = async (sock, m) => {
    const msg = m.messages[0];
    if (!msg.message || msg.key.fromMe) return;
    const remoteJid = msg.key.remoteJid;
    const body = msg.message.conversation || msg.message.extendedTextMessage?.text;
    console.log(`[wa/lib/message_router.js][incoming] 收到来自 ${remoteJid} 的消息: ${body}`);
};

module.exports = { handleIncomingMessage };
