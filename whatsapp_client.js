/**
 * whatsapp_client.js - v6.0
 *
 * CAMBIOS v6.0:
 * - Flujo de bienvenida rediseñado: "Hola" limpia sesion y solicita elegir empresa
 * - Cambio de empresa va DIRECTO a Python via /cambiar_empresa (sin Gemini)
 * - Bloquea consultas hasta que haya empresa valida seleccionada
 * - Logs detallados para diagnostico
 *
 * Estados: BIENVENIDA -> ELEGIR_EMPRESA -> MENU -> IA
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const express = require('express');
const crypto = require('crypto');

// ==========================================
// CONFIGURACION
// ==========================================
// require('dotenv').config(); // Eliminado porque causaba Error: Cannot find module 'dotenv'
const WEBHOOK_URL = 'http://localhost:8199/webhook';
const PYTHON_LOCAL_URL = 'http://localhost:8199';
const CALLBACK_PORT = 3001;
const WHITELIST = ['85440572964888', '158767878549602', '85950952694007']; // Hardcodeado temporalmente por falta de dotenv

// Mapa de nombres amigables -> nombres tecnicos exactos en la DB
const EMPRESAS_VALIDAS = {
    'sba':      'SBA_PROD',
    'ersa':     'ERSA_PRODUCTIVA',
    'ersagro':  'ERSAGRO_PROD',
    'sa':       'SA_PRODUCTIVA',
    'sb':       'SB_PROD',
    'jeuma':    'JEUMA_PRODUCTIVA',
    'ersa test':'ERSA_TESTPB1',
    'ersatest': 'ERSA_TESTPB1',
};

const MENSAJE_ELEGIR_EMPRESA =
    '*Asistente CxC - Bot Financiero*\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n' +
    'Para comenzar, selecciona la empresa con la que deseas trabajar:\n\n' +
    '*1* - SBA\n' +
    '*2* - ERSA\n' +
    '*3* - ERSAGRO\n' +
    '*4* - SA\n' +
    '*5* - SB\n' +
    '*6* - JEUMA\n\n' +
    '_Escribe el numero o el nombre de la empresa_';

const OPCIONES_EMPRESA_NUM = {
    '1': 'SBA_PROD',
    '2': 'ERSA_PRODUCTIVA',
    '3': 'ERSAGRO_PROD',
    '4': 'SA_PRODUCTIVA',
    '5': 'SB_PROD',
    '6': 'JEUMA_PRODUCTIVA',
};

const NOMBRES_DISPLAY = {
    'SBA_PROD':          'SBA',
    'ERSA_PRODUCTIVA':   'ERSA',
    'ERSAGRO_PROD':      'ERSAGRO',
    'SA_PRODUCTIVA':     'SA',
    'SB_PROD':           'SB',
    'JEUMA_PRODUCTIVA':  'JEUMA',
    'ERSA_TESTPB1':      'ERSA Test',
};

// ==========================================
// MAPAS DE ESTADO (in-memory)
// ==========================================
const msgMap = new Map();       // sender -> { msg, timestamp }
const userStates = new Map();   // sender -> { estado, empresa }
const broadcastCache = new Map(); // "destino|hash" -> timestamp

// ==========================================
// CLIENTE DE WHATSAPP
// ==========================================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { args: ['--no-sandbox', '--disable-setuid-sandbox'] }
});

let isClientReady = false;

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('Escanea el QR con WhatsApp para conectar.');
});

client.on('ready', () => {
    isClientReady = true;
    console.log('Cliente de WhatsApp conectado y listo.');
});

client.on('disconnected', (reason) => {
    isClientReady = false;
    console.warn('WhatsApp desconectado:', reason);
});

// ==========================================
// HANDLER PRINCIPAL DE MENSAJES ENTRANTES
// ==========================================
client.on('message', async (msg) => {
    try {
        if (!msg || !msg.from) return;
        if (msg.from === 'status@broadcast') return;
        if (msg.from.endsWith('@g.us')) return;
        if (msg.from.endsWith('@newsletter')) return;
        const senderNumberForCheck = msg.from.split('@')[0];
        const stateForCheck = userStates.get(senderNumberForCheck);
        
        if (msg.hasMedia) { 
            console.log('Multimedia ignorado.'); 
            if (stateForCheck && stateForCheck.estado === 'ELEGIR_EMPRESA') {
                msg.reply('Por favor, responde solo con texto (el número o nombre de la empresa).').catch(()=>{});
            }
            return; 
        }
        if (!msg.body || msg.body.trim() === '') {
            if (stateForCheck && stateForCheck.estado === 'ELEGIR_EMPRESA') {
                msg.reply('Por favor, responde solo con texto (el número o nombre de la empresa).').catch(()=>{});
            }
            return; 
        }

        const senderNumber = msg.from.split('@')[0];
        const messageText = msg.body.trim();

        const now = Date.now();
        for (const [key, value] of msgMap.entries()) {
            if (now - value.timestamp > 3600000) msgMap.delete(key);
        }
        msgMap.set(senderNumber, { msg: msg, timestamp: now });

        const estadoActual = userStates.get(senderNumber) || 'NUEVO';
        console.log('\n[ENTRADA] De: ' + senderNumber);
        console.log('   Texto: "' + messageText.substring(0, 100) + '"');
        console.log('   Estado: ' + JSON.stringify(estadoActual));

        await routeMessage(senderNumber, messageText, msg);

    } catch (error) {
        console.error('Error critico en handler de mensaje:', error.message);
    }
});

client.on('message_create', async (msg) => {
    console.log(`[DEBUG_ALL_MSGS] De: ${msg.from} | Para: ${msg.to} | Body: ${msg.body}`);
});


// ==========================================
// HELPER: resolver nombre de empresa
// ==========================================
function resolverEmpresa(input) {
    // Primero probar por numero (1-6)
    const byNum = OPCIONES_EMPRESA_NUM[input.trim()];
    if (byNum) return byNum;

    // Luego por nombre (busqueda flexible, sin acentos, minusculas)
    const normalizado = input.trim().toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '');

    for (const [clave, valor] of Object.entries(EMPRESAS_VALIDAS)) {
        if (normalizado === clave || normalizado.includes(clave)) return valor;
    }
    return null;
}

// ==========================================
// HELPER: guardar empresa en Python directamente
// ==========================================
async function persistirEmpresa(senderNumber, empresaTecnica) {
    try {
        const resp = await axios.post(PYTHON_LOCAL_URL + '/cambiar_empresa', {
            sender: senderNumber,
            empresa: empresaTecnica
        }, { timeout: 5000 });
        console.log('   [EMPRESA] Guardada en Python: ' + empresaTecnica + ' -> HTTP ' + resp.status);
        return true;
    } catch (e) {
        console.error('   [EMPRESA] Error al persistir en Python: ' + e.message);
        return false;
    }
}

// Auto-registrar como destinatario de broadcast si está en whitelist
async function autoRegistrarDestinatario(senderNumber, originalFrom) {
    // Validar whitelist (permite prefijos de pais) antes de registrar
    const estaPermitido = WHITELIST.some(num => senderNumber.includes(num));
    if (!estaPermitido) return;
    
    const chatId = originalFrom;
    try {
        await axios.post(PYTHON_LOCAL_URL + '/registrar_destinatario', {
            destino: chatId,
            descripcion: 'Auto-registrado'
        }, { timeout: 3000 });
    } catch (e) {
        // No bloquear el flujo principal si falla
    }
}

// ==========================================
// ROUTER: MAQUINA DE ESTADOS v6.0
// ==========================================
async function routeMessage(senderNumber, messageText, msg) {
    // TAREA 1: Auto-registrar destinatario (la funcion misma valida la whitelist)
    autoRegistrarDestinatario(senderNumber, msg.from);

    const textLower = messageText.trim().toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    let state = userStates.get(senderNumber) || { estado: 'NUEVO', empresa: null };

    // ============================================================
    // (A) TRIGGER DE BIENVENIDA: saludos limpian la sesion
    // ============================================================
    const esSaludo = /^(hola|buenos dias|buenas tardes|buenas noches|inicio|start|reiniciar|menu|opciones|ayuda|help|0)$/i.test(textLower);

    if (esSaludo) {
        console.log('   [ROUTER] Saludo detectado — limpiando sesion de ' + senderNumber);

        // Limpiar estado local (empresa persiste en Python hasta que elijan nueva)
        state = { estado: 'ELEGIR_EMPRESA', empresa: null };
        userStates.set(senderNumber, state);

        // Limpiar empresa en Python tambien para forzar seleccion fresca
        try {
            await axios.post(PYTHON_LOCAL_URL + '/cambiar_empresa', {
                sender: senderNumber,
                empresa: null   // null = borrar empresa activa
            }, { timeout: 3000 });
            console.log('   [ROUTER] Empresa borrada en Python para ' + senderNumber);
        } catch (e) {
            console.error('   [ROUTER] Error borrando empresa en Python: ' + e.message);
        }

        console.log('   [ROUTER] Enviando pantalla de seleccion de empresa...');
        try {
            await msg.reply(MENSAJE_ELEGIR_EMPRESA);
            console.log('   [ROUTER] Pantalla enviada OK');
        } catch (err) {
            console.error('   msg.reply() fallo: ' + err.message);
            try { await client.sendMessage(msg.from, MENSAJE_ELEGIR_EMPRESA); } catch (e2) {}
        }
        return;
    }

    // ============================================================
    // (B) ESTADO ELEGIR_EMPRESA — captura y valida empresa
    // ============================================================
    if (state.estado === 'ELEGIR_EMPRESA') {
        console.log('   [ROUTER] Intentando resolver empresa: "' + messageText + '"');

        const empresaTecnica = resolverEmpresa(textLower);

        if (!empresaTecnica) {
            // Empresa no reconocida: pedir de nuevo
            await msg.reply(
                'No reconoci esa empresa. Por favor elige una opcion:\n\n' +
                '*1* - SBA  |  *2* - ERSA  |  *3* - ERSAGRO\n' +
                '*4* - SA   |  *5* - SB    |  *6* - JEUMA\n\n' +
                '_Escribe el numero o el nombre_'
            );
            return;
        }

        // Empresa valida: persistir en Python directamente (sin Gemini)
        await persistirEmpresa(senderNumber, empresaTecnica);
        const nombreDisplay = NOMBRES_DISPLAY[empresaTecnica] || empresaTecnica;

        // Estado pasa a IA directo — usuario puede consultar sin pasar por menu
        state.empresa = empresaTecnica;
        state.estado = 'IA';
        userStates.set(senderNumber, state);

        // Confirmacion breve — sin segundo menu
        await msg.reply('Empresa: *' + nombreDisplay + '* ✅\n\n_Escribe tu consulta financiera o "cambiar" para elegir otra empresa._');
        console.log('   [ROUTER] Empresa anclada: ' + empresaTecnica + ' | estado -> IA');
        return;
    }

    // ============================================================
    // (C) ESTADO MENU — procesar opcion
    // ============================================================
    if (state.estado === 'MENU') {
        console.log('   [ROUTER] En MENU, opcion: "' + textLower + '"');

        // Sin empresa: forzar seleccion
        if (!state.empresa) {
            state.estado = 'ELEGIR_EMPRESA';
            userStates.set(senderNumber, state);
            await msg.reply('Primero necesitas seleccionar una empresa.\n\n' + MENSAJE_ELEGIR_EMPRESA);
            return;
        }

        const nombreDisplay = NOMBRES_DISPLAY[state.empresa] || state.empresa;

        if (textLower === '1' || textLower.includes('saldo') || textLower.includes('cliente')) {
            state.estado = 'IA';
            userStates.set(senderNumber, state);
            await msg.reply('*Consulta de Saldo* [' + nombreDisplay + ']\n\nEscribe tu pregunta.\n_Ejemplo: "Cuanto nos debe Costco?" o "saldo de FGR"_');
            return;
        }

        if (textLower === '2' || textLower.includes('pendientes') || textLower.includes('facturas')) {
            console.log('   [ROUTER] Opcion 2: /facturas_pendientes');
            try { await msg.reply('Consultando facturas pendientes de *' + nombreDisplay + '*...\nDame un momento.'); } catch (e) {}
            axios.post(PYTHON_LOCAL_URL + '/facturas_pendientes', { sender: senderNumber }, { timeout: 5000 })
                .then(r => console.log('   /facturas_pendientes: ' + r.status))
                .catch(err => console.error('   Error /facturas_pendientes: ' + err.message));
            return;
        }

        if (textLower === '3' || textLower.includes('agente') || textLower.includes('ia') || textLower.includes('consulta')) {
            state.estado = 'IA';
            userStates.set(senderNumber, state);
            await msg.reply('*Agente IA* [' + nombreDisplay + ']\n\nEscribe cualquier pregunta financiera.\n_Para volver al menu escribe "menu"_');
            return;
        }

        if (textLower === '4' || textLower.includes('cambiar') || textLower.includes('empresa')) {
            state.estado = 'ELEGIR_EMPRESA';
            state.empresa = null;
            userStates.set(senderNumber, state);
            await msg.reply(MENSAJE_ELEGIR_EMPRESA);
            return;
        }

        // Texto libre en estado MENU -> enviar a Gemini directamente (el usuario ya eligio empresa)
        console.log('   [ROUTER] Texto libre en MENU -> redirigiendo a Gemini');
        state.estado = 'IA';
        userStates.set(senderNumber, state);
        axios.post(WEBHOOK_URL, {
            sender: senderNumber,
            message: messageText
        }, { timeout: 15000 }).then(r => {
            console.log('   [ROUTER] Webhook acepto texto libre desde MENU (HTTP ' + r.status + ')');
        }).catch(err => {
            console.error('   [ROUTER] Error al webhook desde MENU: ' + err.message);
            msg.reply('⚠️ No pude procesar tu consulta ahora mismo. Inténtalo de nuevo en unos segundos.').catch(() => {});
        });
        return;
    }

    // ============================================================
    // (D) ESTADO IA — consultas van a Gemini
    // ============================================================

    // Sin empresa: bloquear y forzar seleccion
    if (!state.empresa) {
        state.estado = 'ELEGIR_EMPRESA';
        userStates.set(senderNumber, state);
        await msg.reply('Para hacer consultas primero debes seleccionar una empresa.\n\n' + MENSAJE_ELEGIR_EMPRESA);
        return;
    }

    console.log('   [ROUTER] Enviando a Gemini [' + state.empresa + ']: "' + messageText.substring(0, 60) + '"');
    state.estado = 'IA';
    userStates.set(senderNumber, state);

    axios.post(WEBHOOK_URL, {
        sender: senderNumber,
        message: messageText
    }, { timeout: 15000 }).then(r => {
        console.log('   [ROUTER] Webhook acepto (HTTP ' + r.status + ')');
    }).catch(err => {
        console.error('   [ROUTER] Error al webhook: ' + err.message);
        msg.reply('⚠️ No pude procesar tu consulta ahora mismo. Inténtalo de nuevo en unos segundos.').catch(() => {});
    });
}

// ==========================================
// SERVIDOR EXPRESS - Callbacks desde Python
// ==========================================
const callbackApp = express();
callbackApp.use(express.json());

callbackApp.post('/send-reply', async (req, res) => {
    const { to, message } = req.body;
    if (!to || !message) return res.status(400).json({ error: 'Faltan to y message.' });

    const cleanMessage = message.replace(/\\n/g, '\n').replace(/\*\*/g, '*');
    console.log('\n[SEND-REPLY] Para: ' + to);
    console.log('   "' + cleanMessage.substring(0, 100) + '..."');

    const savedData = msgMap.get(to);
    if (savedData && savedData.msg) {
        try {
            await savedData.msg.reply(cleanMessage);
            console.log('   [SEND-REPLY] OK via msg.reply()');
            return res.json({ status: 'sent', method: 'reply' });
        } catch (err1) {
            console.warn('   msg.reply() fallo: ' + err1.message);
        }
    } else {
        console.warn('   Sin msg guardado para ' + to);
    }

    try {
        const chatId = to.includes('@') ? to : to + '@c.us';
        await client.sendMessage(chatId, cleanMessage);
        console.log('   [SEND-REPLY] OK via sendMessage() (fallback)');
        return res.json({ status: 'sent', method: 'sendMessage' });
    } catch (err2) {
        console.error('   Ambos metodos fallaron: ' + err2.message);
        return res.status(500).json({ error: err2.message });
    }
});

callbackApp.post('/broadcast', async (req, res) => {
    const { targets, message } = req.body;
    if (!Array.isArray(targets) || targets.length === 0 || !message) {
        return res.status(400).json({ error: 'Faltan targets y message.' });
    }

    const cleanMessage = message.replace(/\\n/g, '\n').replace(/\*\*/g, '*');
    const msgHash = crypto.createHash('md5').update(cleanMessage).digest('hex');
    const results = [];

    const currentNow = Date.now();
    for (const [key, ts] of broadcastCache.entries()) {
        if (currentNow - ts > 10 * 60 * 1000) broadcastCache.delete(key);
    }
    console.log('\n[BROADCAST] Para ' + targets.length + ' destinatario(s)');

    for (let i = 0; i < targets.length; i++) {
        const targetObj = targets[i];
        const destino = typeof targetObj === 'string' ? targetObj : targetObj.destino;
        const nombre = typeof targetObj === 'string' ? '' :
            (targetObj.descripcion ? targetObj.descripcion.split(' ')[0] : '');

        const cacheKey = destino + '|' + msgHash;
        const now = Date.now();

        if (broadcastCache.has(cacheKey) && (now - broadcastCache.get(cacheKey) < 5 * 60 * 1000)) {
            results.push({ target: destino, status: 'skipped', reason: 'duplicate' });
            continue;
        }

        const finalMsg = nombre ? 'Hola ' + nombre + ',\n' + cleanMessage : cleanMessage;
        try {
            const savedData = msgMap.get(destino.split('@')[0]);
            if (savedData && savedData.msg) {
                try {
                    const chat = await savedData.msg.getChat();
                    await chat.sendMessage(finalMsg);
                    broadcastCache.set(cacheKey, now);
                    results.push({ target: destino, status: 'sent', method: 'msgMap_chat' });
                    continue;
                } catch(e) {
                    console.warn('   [BROADCAST] msgMap getChat fallo, intentando fallback: ' + e.message);
                }
            }

            let finalDestino = destino;
            try {
                const numberOnly = destino.split('@')[0];
                const isRegistered = await client.isRegisteredUser(numberOnly);
                if (isRegistered) {
                    const numberId = await client.getNumberId(numberOnly);
                    if (numberId && numberId._serialized) {
                        finalDestino = numberId._serialized;
                    }
                }
            } catch(e) {
                console.warn('   [BROADCAST] Error en isRegisteredUser: ' + e.message);
            }
            
            let chat;
            try {
                const contact = await client.getContactById(finalDestino);
                chat = await contact.getChat();
                await chat.sendMessage(finalMsg);
            } catch (chatErr) {
                // Si falla, intentamos client.sendMessage directo con el destino original
                await client.sendMessage(finalDestino, finalMsg);
            }
            broadcastCache.set(cacheKey, now);
            results.push({ target: destino, status: 'sent' });
        } catch (err) {
            results.push({ target: destino, status: 'failed', error: err.message });
        }

        if (i < targets.length - 1) {
            await new Promise(r => setTimeout(r, Math.floor(Math.random() * 2000) + 1500));
        }
    }
    return res.json({ results });
});

callbackApp.get('/health', (req, res) => {
    res.json({
        status: 'ok', version: '6.0', port: CALLBACK_PORT,
        whatsapp_ready: isClientReady,
        chats_activos: msgMap.size,
        usuarios_con_estado: userStates.size
    });
});

// ==========================================
// ARRANQUE
// ==========================================
callbackApp.listen(CALLBACK_PORT, () => {
    console.log('Callback server en http://localhost:' + CALLBACK_PORT);
});

client.initialize();
console.log('Inicializando cliente WhatsApp v6.0...');
