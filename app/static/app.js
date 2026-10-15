/* Descarregador de Fotos - versao Web (SPA sem build) */
const $app = document.getElementById('app');
const $modal = document.getElementById('modal-root');
const S = { view: 'home', st: null, editId: null, form: null, sel: {}, origem: null, poll: null };

// ---------- utilidades ----------
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
async function api(url, opts = {}) {
  const o = { method: opts.method || 'GET', headers: {} };
  if (opts.body !== undefined) { o.body = JSON.stringify(opts.body); o.headers['Content-Type'] = 'application/json'; if (!opts.method) o.method = 'POST'; }
  const r = await fetch(url, o);
  let d = null; try { d = await r.json(); } catch (e) { }
  if (!r.ok) throw new Error((d && (d.detail || d.erro)) || ('Erro ' + r.status));
  return d;
}
function toast(msg, err) {
  const t = document.createElement('div'); t.className = 'toast' + (err ? ' err' : ''); t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), err ? 6000 : 3500);
}
function modal(html, botoes, larga) {
  return new Promise(res => {
    const bg = document.createElement('div'); bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal ${larga ? 'larga' : ''}"><div class="mc">${html}</div><div class="btns"></div></div>`;
    const btns = bg.querySelector('.btns');
    botoes.forEach(b => {
      const el = document.createElement('button'); el.textContent = b.t; if (b.c) el.className = b.c;
      el.onclick = () => { bg.remove(); res(b.v); }; btns.appendChild(el);
    });
    $modal.appendChild(bg);
  });
}
const alerta = (t, m) => modal(`<h2>${esc(t)}</h2>${esc(m)}`, [{ t: 'OK', v: true }]);
const confirmar = (t, m, sim = 'Sim', nao = 'Não') => modal(`<h2>${esc(t)}</h2>${esc(m)}`, [{ t: nao, v: false, c: 'cinza' }, { t: sim, v: true }]);
const tri = (t, m, a, b, c) => modal(`<h2>${esc(t)}</h2>${esc(m)}`, [{ t: c, v: null, c: 'cinza' }, { t: b, v: false, c: 'verm' }, { t: a, v: true, c: 'verde' }]);

// seletor de pasta do servidor (o navegador nao enxerga o disco da maquina)
function escolherPasta(titulo, inicio) {
  return new Promise(async res => {
    const bg = document.createElement('div'); bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal larga"><h2>${esc(titulo)}</h2><div class="path" id="fs-p"></div>
      <div class="chips" id="fs-at"></div><div class="fs-list" id="fs-l"></div>
      <div class="btns"><button class="cinza pq" id="fs-new">+ Nova pasta</button><span style="flex:1"></span>
      <button class="cinza" id="fs-c">Cancelar</button><button class="verde" id="fs-ok">Selecionar esta pasta</button></div></div>`;
    $modal.appendChild(bg);
    let atual = inicio || '';
    const $ = id => bg.querySelector(id);
    async function ir(p) {
      try {
        const d = await api('/api/fs/list?path=' + encodeURIComponent(p || '')); atual = d.path;
        $('#fs-p').textContent = d.path;
        $('#fs-at').innerHTML = d.atalhos.map((a, i) => `<span class="chip" style="cursor:pointer" data-a="${i}">📌 ${esc(a.nome)}</span>`).join('');
        $('#fs-at').querySelectorAll('[data-a]').forEach(e => e.onclick = () => ir(d.atalhos[e.dataset.a].caminho));
        $('#fs-l').innerHTML = `<div data-p="${esc(d.parent)}">⬆️ ..</div>` + d.pastas.map(n => `<div data-n="${esc(n)}">📁 ${esc(n)}</div>`).join('');
        $('#fs-l').querySelector('[data-p]').onclick = () => ir(d.parent);
        $('#fs-l').querySelectorAll('[data-n]').forEach(e => e.onclick = () => ir(d.path.replace(/[\\/]$/, '') + (d.path.includes('\\') ? '\\' : '/') + e.dataset.n));
      } catch (e) { toast(e.message, true); }
    }
    $('#fs-c').onclick = () => { bg.remove(); res(null); };
    $('#fs-ok').onclick = () => { bg.remove(); res(atual); };
    $('#fs-new').onclick = async () => {
      const nome = prompt('Nome da nova pasta:'); if (!nome) return;
      try { const d = await api('/api/fs/mkdir', { body: { path: atual, nome } }); ir(d.path); } catch (e) { toast(e.message, true); }
    };
    ir(inicio);
  });
}

async function carregar() { S.st = await api('/api/state'); const b = document.getElementById('banner'); const u = S.st.update;
  if (S.st.precisa_reiniciar) { b.classList.remove('hidden'); b.style.background = 'var(--lar)'; b.innerHTML = '⚠️ O programa foi atualizado. <b>Feche o servidor (Ctrl+C no terminal) e abra de novo</b> (rodar.sh / rodar.bat) para aplicar as mudanças.'; }
  else if (u && u.disponivel && u.url) { b.style.background = ''; b.classList.remove('hidden');   // programa instalado: baixa o novo instalador
    b.innerHTML = `${esc(u.msg)} <button id="b-up">⬇ Baixar nova versão</button>`; document.getElementById('b-up').onclick = () => window.open(u.url, '_blank'); }
  else if (u && u.disponivel) { b.style.background = ''; b.classList.remove('hidden'); b.innerHTML = `${esc(u.msg)} <button id="b-up">Atualizar agora</button>`;
    document.getElementById('b-up').onclick = async () => { try { const r = await api('/api/update/aplicar', { body: {} }); toast(r.msg); b.classList.add('hidden'); } catch (e) { toast(e.message, true); } };
  } else b.classList.add('hidden'); }
function ir(v) { S.view = v; pararPoll(); render(); }
function pararPoll() { if (S.poll) { clearInterval(S.poll); S.poll = null; } }
function iniciarPoll(fn, ms) { pararPoll(); S.poll = setInterval(fn, ms); }
async function render() {
  try { await carregar(); } catch (e) { $app.innerHTML = `<div class="wrap"><p class="bad">Servidor indisponível: ${esc(e.message)}</p></div>`; return; }
  if (S.st.servir_finalizado_remotamente) {
    await api('/api/ack-finalizado', { body: {} }); S.st.active_servir = null;
    await alerta('Servir Finalizado', 'O computador Líder finalizou o Dia de Servir.\nSua estação foi desconectada automaticamente.'); S.view = 'home';
  }
  if (S.view === 'home' && (S.st.active_servir || S.avulso) && S.entrou) S.view = 'descarregar';
  ({ home: vHome, descarregar: vDescarregar, historico: vHistorico, drive: vDrive, google: vGoogle, predef: vPredef }[S.view] || vHome)();
}

// cria no Drive as pastas de categoria do Servir (com a data de hoje) assim que ele comeca; nao bloqueia a tela
async function criarPastasDriveAuto(sv) {
  if (!sv || !sv.drive_criar_categorias || !(sv.pastas_predefinidas || []).length || !(sv.drive_folders || []).length) return;
  toast('☁️ Criando as pastas de categoria no Google Drive...');
  try {
    const r = (await api(`/api/servir/${sv.id}/drive-pastas`, { body: {} })).resultado, falhas = r.filter(x => !x.ok);
    if (falhas.length) toast(`⚠️ Drive: ${falhas.length} de ${r.length} pastas com erro (${falhas[0].erro})`, true);
    else toast(`☁️ ${[...new Set(r.map(x => x.pasta))].length} pasta(s) criadas no Drive e salvas em "Pastas do Google Drive" do Servir`);
  } catch (e) { toast('⚠️ Pastas no Drive: ' + e.message, true); }
}

// ---------- painel de acompanhamento: QR code que abre o painel em qualquer celular da mesma rede ----------
async function mostrarQR() {
  let info; try { info = await api('/api/painel/info'); } catch (e) { return toast(e.message, true); }
  const bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal qr-modal"><h2>📱 Painel de acompanhamento</h2>
    <p class="mut mini">Escaneie com o celular (conectado na <b>mesma rede</b> deste computador) para acompanhar quem está descarregando, os PCs livres e quem ainda falta.</p>
    <div class="qr-box"><img id="qr-img" alt="QR code do painel"></div>
    <div class="path" id="qr-url" style="text-align:center"></div>
    ${info.ips.length > 1 ? `<p class="mut mini">Não abriu? Este computador tem mais de uma rede; escolha a que os celulares usam:</p><div class="chips" id="qr-ips">${info.ips.map((ip, i) => `<span class="chip" style="cursor:pointer" data-i="${i}">${esc(ip)}</span>`).join('')}</div>` : ''}
    <div class="btns"><a id="qr-abrir" target="_blank" rel="noopener"><button class="cinza">Abrir painel aqui</button></a><button id="qr-ok">Fechar</button></div></div>`;
  $modal.appendChild(bg);
  const $ = x => bg.querySelector(x);
  const usa = i => {
    $('#qr-img').src = '/api/painel/qr.svg?ip=' + encodeURIComponent(info.ips[i]); $('#qr-url').textContent = info.urls[i]; $('#qr-abrir').href = info.urls[i];
    bg.querySelectorAll('#qr-ips [data-i]').forEach(c => c.classList.toggle('sel', +c.dataset.i === i));
  };
  bg.querySelectorAll('#qr-ips [data-i]').forEach(c => c.onclick = () => usa(+c.dataset.i));
  $('#qr-ok').onclick = () => bg.remove();
  usa(0);
}
// conta para o painel que este PC esta ocupado (e por quem); falha aqui nunca atrapalha o descarregamento
const avisarAtividade = voluntario => api('/api/atividade', { body: { acao: 'ocupar', voluntario } }).catch(() => { });

// ---------- predefinicoes de categorias: janela so de SELECAO (o cadastro fica na tela "Predefinições") ----------
async function abrirPredefinicoes(jaTem) {
  let lista; try { lista = await api('/api/predefinicoes'); } catch (e) { toast(e.message, true); return null; }
  return new Promise(res => {
    const bg = document.createElement('div'); bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal larga"><h2>📋 Predefinições de categorias</h2><p class="mut mini">Marque o grupo para selecionar todas as pastas dele; clique numa pasta para tirá-la da seleção.</p>
      <div id="pd-corpo"></div><div class="btns"><button class="cinza" id="pd-x">Cancelar</button><button class="verde" id="pd-ok" disabled>Adicionar selecionadas</button></div></div>`;
    $modal.appendChild(bg);
    const sel = lista.map(() => new Set()), corpo = bg.querySelector('#pd-corpo'), ok = bg.querySelector('#pd-ok');
    function desenha() {
      corpo.innerHTML = lista.map((p, i) => {
        const livres = p.pastas.filter(n => !jaTem.includes(n)), marc = livres.filter(n => sel[i].has(n)).length;
        return `<div class="pd"><div class="pd-h"><label><input type="checkbox" data-p="${i}" ${livres.length && marc === livres.length ? 'checked' : ''} ${livres.length ? '' : 'disabled'}> <b>${esc(p.titulo)}</b></label></div>
          <div class="pd-c">${p.pastas.map(n => jaTem.includes(n) ? `<label class="mut"><input type="checkbox" checked disabled> ${esc(n)} <small>(já adicionada)</small></label>`
            : `<label><input type="checkbox" data-c="${i}|${esc(n)}" ${sel[i].has(n) ? 'checked' : ''}> ${esc(n)}</label>`).join('')}</div></div>`;
      }).join('') || '<p class="mut">Nenhuma predefinição criada. Use o botão "📋 Predefinições" do menu superior para criar.</p>';
      corpo.querySelectorAll('[data-p]').forEach(cb => {
        const i = +cb.dataset.p, livres = lista[i].pastas.filter(n => !jaTem.includes(n)), marc = livres.filter(n => sel[i].has(n)).length;
        cb.indeterminate = marc > 0 && marc < livres.length;
        cb.onchange = () => { sel[i] = new Set(cb.checked ? livres : []); desenha(); };
      });
      corpo.querySelectorAll('[data-c]').forEach(cb => cb.onchange = () => { const [i, n] = cb.dataset.c.split('|'); cb.checked ? sel[+i].add(n) : sel[+i].delete(n); desenha(); });
      const total = new Set(sel.flatMap(x => [...x])).size;
      ok.disabled = !total; ok.textContent = total ? `Adicionar ${total} selecionada(s)` : 'Adicionar selecionadas';
    }
    bg.querySelector('#pd-x').onclick = () => { bg.remove(); res(null); };
    ok.onclick = () => { const r = [...new Set(sel.flatMap(x => [...x]))]; bg.remove(); res(r); };
    desenha();
  });
}

// ---------- tela de cadastro das predefinicoes (criar, editar, excluir) ----------
async function vPredef(cache) {
  // `cache`: lista ja carregada (redesenhos de edicao nao precisam buscar no servidor de novo)
  let lista = cache; if (!lista) { try { lista = await api('/api/predefinicoes'); } catch (e) { return alerta('Erro', e.message); } }
  const ed = S.pdEd || null;
  const salvar = async nova => { try { await api('/api/predefinicoes', { method: 'PUT', body: nova }); return true; } catch (e) { toast(e.message, true); return false; } };
  $app.innerHTML = `<div class="wrap" style="max-width:760px"><div class="topbar"><h1>📋 Predefinições de categorias</h1><div class="acts"><button class="cinza" id="pr-v">⬅ Voltar</button></div></div>
  <p class="mut">Uma predefinição é um grupo de pastas de categoria (ex.: <b>ELEVE</b> → Voltz, Bold, Burn, A3). No painel inicial, o botão "📋 Predefinições" ao lado das categorias permite escolher quais usar.</p>
  ${ed ? `<div class="card"><h2>${ed.i === null ? 'Nova predefinição' : 'Editar predefinição'}</h2>
     <label>Título</label><input type="text" id="pd-t" value="${esc(ed.titulo)}" placeholder="Ex.: ELEVE">
     <label>Nomes das pastas</label><div class="row"><input type="text" id="pd-n" placeholder="Nome da pasta"><button class="fix" id="pd-add">Adicionar</button></div>
     <div class="chips">${ed.pastas.map((n, k) => `<span class="chip">${esc(n)} <b data-r="${k}">✕</b></span>`).join('') || '<span class="mut mini">Nenhuma pasta</span>'}</div>
     <div class="nav"><button class="cinza" id="pd-cancel">Cancelar</button><button class="verde" id="pd-save">💾 Salvar predefinição</button></div></div>`
  : `${lista.map((p, i) => `<div class="pd"><div class="pd-h"><b>${esc(p.titulo)}</b><span><button class="pq cinza" data-e="${i}">Editar</button> <button class="pq verm" data-x="${i}">Excluir</button></span></div>
      <div class="chips">${p.pastas.map(n => `<span class="chip">${esc(n)}</span>`).join('')}</div></div>`).join('') || '<p class="mut">Nenhuma predefinição criada.</p>'}
     <button class="verde grande" id="pd-new" style="margin-top:12px">＋ Nova predefinição</button>`}</div>`;
  const q = x => $app.querySelector(x);
  q('#pr-v').onclick = () => { S.pdEd = null; ir('home'); };
  if (ed) {
    const add = () => { ed.titulo = q('#pd-t').value; const v = q('#pd-n').value.trim(); if (v && !ed.pastas.includes(v)) ed.pastas.push(v); vPredef(lista); };
    q('#pd-add').onclick = add; q('#pd-n').onkeydown = e => { if (e.key === 'Enter') add(); };
    $app.querySelectorAll('[data-r]').forEach(b => b.onclick = () => { ed.titulo = q('#pd-t').value; ed.pastas.splice(+b.dataset.r, 1); vPredef(lista); });
    q('#pd-cancel').onclick = () => { S.pdEd = null; vPredef(lista); };
    q('#pd-save').onclick = async () => {
      ed.titulo = q('#pd-t').value; const pend = q('#pd-n').value.trim(); if (pend && !ed.pastas.includes(pend)) ed.pastas.push(pend);
      const nova = lista.map(x => ({ ...x })), item = { titulo: ed.titulo.trim(), pastas: ed.pastas };
      if (ed.i === null) nova.push(item); else nova[ed.i] = item;
      if (await salvar(nova)) { S.pdEd = null; toast('Predefinição salva!'); vPredef(); }
    };
  } else {
    q('#pd-new').onclick = () => { S.pdEd = { i: null, titulo: '', pastas: [] }; vPredef(lista); };
    $app.querySelectorAll('[data-e]').forEach(b => b.onclick = () => { const p = lista[+b.dataset.e]; S.pdEd = { i: +b.dataset.e, titulo: p.titulo, pastas: [...p.pastas] }; vPredef(lista); });
    $app.querySelectorAll('[data-x]').forEach(b => b.onclick = async () => {
      const p = lista[+b.dataset.x];
      if (await confirmar('Excluir predefinição', `Excluir a predefinição "${p.titulo}"?\n\nIsso não apaga nenhuma pasta já criada.`, 'Excluir', 'Cancelar') && await salvar(lista.filter((_, k) => k !== +b.dataset.x))) vPredef();
    });
  }
}

// ---------- HOME ----------
function formVazio() { return { nome: '', voluntarios: [], pastas: [], drives: [], local: '', criarDrive: false }; }
async function vHome() {
  const st = S.st; S.entrou = false; S.avulso = false;
  if (!S.form) S.form = formVazio();
  const dias = await api('/api/servir'); const f = S.form; const editando = !!S.editId;
  const r = st.rede;
  $app.innerHTML = `<div class="wrap">
  <div class="topbar"><div><h1>📸 Descarregador de Fotos — Painel Inicial</h1><div class="mut mini">Versão ${esc(st.versao)}</div></div>
   <div class="acts"><button data-go="google">🔑 Login Google</button><button data-go="predef">📋 Predefinições</button><button data-go="historico">📊 Histórico</button><button data-go="drive">⚙️ Config Drive</button><button class="verm" id="b-sair" title="Fecha o programa neste computador">⏻ Encerrar</button></div></div>
  <div class="grid"><div>
    <div class="card"><h2 class="${editando ? 'warn' : 'ok'}">${editando ? '✏️ Editando Dia do Servir' : 'Criar Novo Dia do Servir'}</h2>
     <label>Nome do Servir</label><input type="text" id="f-nome" value="${esc(f.nome)}" placeholder="Ex.: Culto de Domingo">
     <label>Voluntários (fotógrafos)</label>
     <div class="row"><input type="text" id="f-vol" placeholder="Nome do voluntário"><button class="fix" id="a-vol">Adicionar</button></div>
     <div class="chips">${f.voluntarios.map((v, i) => `<span class="chip">${esc(v)} <b data-rv="${i}">✕</b></span>`).join('') || '<span class="mut mini">Nenhum voluntário</span>'}</div>
     <label>Pastas de categoria (opcional)</label>
     <div class="row"><input type="text" id="f-pasta" placeholder="Ex.: Louvor, Pregação"><button class="fix" id="a-pasta">Adicionar</button><button class="fix cinza" id="a-pred" title="Adicionar um grupo de categorias pronto">📋 Predefinições</button></div>
     <div class="chips">${f.pastas.map((v, i) => `<span class="chip">${esc(v)} <b data-rp="${i}">✕</b></span>`).join('') || '<span class="mut mini">Nenhuma pasta</span>'}</div>
     <label>Pastas do Google Drive (opcional)</label>
     <div class="row"><input type="text" id="f-dl" placeholder="Link da pasta do Drive"><input type="text" id="f-dn" placeholder="Nome (opcional)"><button class="fix" id="a-dr">Adicionar</button></div>
     ${f.drives.map((d, i) => `<div class="item"><span class="t">☁️ ${esc(d.nome)}${d.auto ? ' <span class="chip mini">criada automaticamente</span>' : ''}<br><span class="mut mini">${esc(d.link)}</span></span><button class="verm pq" data-rd="${i}">Remover</button></div>`).join('')}
     <label style="font-weight:400;display:flex;gap:8px;align-items:flex-start;margin-top:10px"><input type="checkbox" id="f-cdrive" style="margin-top:4px" ${f.criarDrive ? 'checked' : ''}><span>Usar a pasta do Drive como <b>pasta base</b>: criar nela, <b>automaticamente ao iniciar o Servir</b>, as pastas de categoria (com a data de hoje) e adicioná-las às pastas do Drive do Servir, para escolher o destino ao enviar as fotos</span></label>
     <label>Pasta local do evento (opcional)</label>
     <div class="row"><input type="text" id="f-local" value="${esc(f.local)}" placeholder="Padrão: pasta do aplicativo"><button class="fix cinza" id="p-local">Procurar</button></div>
     <div style="margin-top:14px" class="row"><button class="verde grande" id="b-salvar">${editando ? '💾 Salvar Alterações' : '🚀 Criar e Ativar Novo Servir'}</button>${editando ? '<button class="cinza grande fix" id="b-canc" style="width:auto">Cancelar</button>' : ''}</div>
    </div>
    <button class="cinza grande" id="b-avulso">📂 Modo Avulso (Sem Dia de Servir)</button>
  </div><div>
    <div class="card"><h2>Dias de Servir Anteriores</h2>
     ${dias.slice().reverse().map(d => `<div class="item"><span class="t"><b>${esc(d.nome)}</b><br><span class="mut mini">${esc(d.data_criacao || '')} · ${d.voluntarios.length} voluntário(s)</span></span>
       <button class="verde pq" data-at="${esc(d.id)}">Ativar</button><button class="pq" data-ed="${esc(d.id)}">Editar</button><button class="verm pq" data-ex="${esc(d.id)}">Excluir</button></div>`).join('') || '<p class="mut">Nenhum dia de servir criado ainda.</p>'}
    </div>
    <div class="card"><h2>🌐 Rede Local (várias estações)</h2>
     <div class="row"><select id="n-modo"><option value="lider" ${r.modo === 'lider' ? 'selected' : ''}>Estação Líder</option><option value="auxiliar" ${r.modo === 'auxiliar' ? 'selected' : ''}>Estação Auxiliar</option></select><button class="fix cinza" id="n-rein">Reiniciar rede</button></div>
     <p class="mut mini">Este computador: ${esc(r.ip)}:${r.porta}</p>
     ${r.modo === 'lider' ? `<h3>Estações conectadas</h3>${r.auxiliares.map(a => `<div class="item"><span>💻 ${esc(a.nome)} (${esc(a.ip)}) <span class="mini ${a.versao === st.versao ? 'mut' : 'warn'}">${a.versao ? 'v' + esc(a.versao) : 'versão desconhecida'}${a.versao === st.versao ? '' : ' ⚠️ diferente deste PC (v' + esc(st.versao) + ') — atualize'}</span></span><span class="ok mini">🟢 Conectado</span></div>`).join('') || '<p class="mut mini">Nenhuma estação conectada. Ative um Servir para transmitir na rede.</p>'}`
      : (r.lider ? `<p class="ok">🟢 LÍDER ENCONTRADO!</p><p>Evento: <b>${esc(r.lider.nome_evento)}</b><br><span class="mut mini">Líder IP: ${esc(r.lider.ip)}:${r.lider.port}</span></p><button class="verde" id="n-sync">🔗 Conectar e Sincronizar</button>`
        : '<p class="warn">🔍 Procurando Líder na rede local...</p>')}
    </div></div></div></div>`;
  const q = s => $app.querySelector(s), qa = s => $app.querySelectorAll(s);
  const ler = () => { f.nome = q('#f-nome').value; f.local = q('#f-local').value; f.criarDrive = q('#f-cdrive').checked; };
  qa('[data-go]').forEach(b => b.onclick = () => ir(b.dataset.go));
  q('#a-vol').onclick = () => { ler(); const v = q('#f-vol').value.trim(); if (v && !f.voluntarios.includes(v)) f.voluntarios.push(v); vHome(); };
  q('#f-vol').onkeydown = e => { if (e.key === 'Enter') q('#a-vol').click(); };
  q('#a-pasta').onclick = () => { ler(); const v = q('#f-pasta').value.trim(); if (v && !f.pastas.includes(v)) f.pastas.push(v); vHome(); };
  q('#f-pasta').onkeydown = e => { if (e.key === 'Enter') q('#a-pasta').click(); };
  q('#a-pred').onclick = async () => { ler(); const novas = await abrirPredefinicoes(f.pastas); if (novas) novas.forEach(n => { if (!f.pastas.includes(n)) f.pastas.push(n); }); vHome(); };
  q('#a-dr').onclick = async () => {
    ler(); const link = q('#f-dl').value.trim(); let nome = q('#f-dn').value.trim(); if (!link) return;
    if (!nome) { try { nome = (await api('/api/drive/nome-pasta?link=' + encodeURIComponent(link))).nome || ''; } catch (e) { } }
    f.drives.push({ link, nome: nome || 'Pasta do Google Drive' }); vHome();
  };
  qa('[data-rv]').forEach(b => b.onclick = () => { ler(); f.voluntarios.splice(b.dataset.rv, 1); vHome(); });
  qa('[data-rp]').forEach(b => b.onclick = () => { ler(); f.pastas.splice(b.dataset.rp, 1); vHome(); });
  qa('[data-rd]').forEach(b => b.onclick = () => { ler(); f.drives.splice(b.dataset.rd, 1); vHome(); });
  q('#p-local').onclick = async () => { ler(); const p = await escolherPasta('Pasta local do evento', f.local); if (p) { f.local = p; vHome(); } };
  q('#b-salvar').onclick = async () => {
    ler(); const pend = q('#f-dl').value.trim();
    if (pend && !f.drives.some(d => d.link === pend)) f.drives.push({ link: pend, nome: q('#f-dn').value.trim() || 'Pasta do Google Drive' });
    const body = { nome: f.nome, voluntarios: f.voluntarios, pastas_predefinidas: f.pastas, drive_folders: f.drives, local_path: f.local, drive_criar_categorias: f.criarDrive };
    try {
      const querDrive = f.criarDrive && f.drives.length && f.pastas.length;
      if (f.criarDrive && !querDrive) toast('Para criar as pastas no Drive, informe a pasta do Drive e ao menos uma pasta de categoria.', true);
      const sv = editando ? await api('/api/servir/' + S.editId, { method: 'PUT', body }) : await api('/api/servir', { body });
      criarPastasDriveAuto(sv);
      if (editando) { toast('Dia do Servir editado com sucesso!'); S.editId = null; S.form = formVazio(); vHome(); }
      else { S.form = formVazio(); S.entrou = true; S.qr = true; ir('descarregar'); }
    } catch (e) { toast(e.message, true); }
  };
  if (editando) q('#b-canc').onclick = () => { S.editId = null; S.form = formVazio(); vHome(); };
  qa('[data-at]').forEach(b => b.onclick = async () => { try { const sv = await api('/api/servir/' + b.dataset.at + '/ativar', { body: {} }); criarPastasDriveAuto(sv); S.entrou = true; S.qr = true; ir('descarregar'); } catch (e) { toast(e.message, true); } });
  qa('[data-ed]').forEach(b => b.onclick = () => {
    const d = dias.find(x => x.id === b.dataset.ed); S.editId = d.id;
    S.form = { nome: d.nome, voluntarios: [...d.voluntarios], pastas: [...(d.pastas_predefinidas || [])], drives: JSON.parse(JSON.stringify(d.drive_folders || [])), local: d.local_path || '', criarDrive: !!d.drive_criar_categorias };
    vHome(); window.scrollTo(0, 0);
  });
  qa('[data-ex]').forEach(b => b.onclick = async () => {
    const d = dias.find(x => x.id === b.dataset.ex);
    if (await confirmar('Confirmar Exclusão', `Deseja realmente excluir a configuração do dia de servir '${d.nome}'?\n\nEsta ação apagará apenas esta configuração no painel, sem apagar nenhuma foto salva.`)) {
      await api('/api/servir/' + d.id, { method: 'DELETE' }); vHome();
    }
  });
  q('#b-sair').onclick = async () => {
    if (!await confirmar('Encerrar programa', 'Fechar o Descarregador de Fotos neste computador?\n\nEnvios ao Drive em andamento serão interrompidos. Para abrir de novo, clique no ícone do programa.', 'Encerrar', 'Cancelar')) return;
    try { await api('/api/encerrar', { body: {} }); } catch (e) { }
    pararPoll(); $app.innerHTML = '<div class="wrap"><div class="card"><h2>Programa encerrado</h2><p class="mut">Pode fechar esta aba. Para abrir de novo, clique no ícone do Descarregador de Fotos.</p></div></div>';
    S.encerrado = true;
  };
  q('#b-avulso').onclick = async () => { await api('/api/avulso', { body: {} }); S.avulso = true; S.entrou = true; ir('descarregar'); };
  q('#n-modo').onchange = async e => { ler(); await api('/api/rede/modo', { body: { modo: e.target.value } }); await carregar(); vHome(); };
  q('#n-rein').onclick = async () => { await api('/api/rede/reiniciar', { body: {} }); toast('Serviços de rede local reiniciados com sucesso!'); await carregar(); vHome(); };
  const sync = q('#n-sync'); if (sync) sync.onclick = async () => { try { await api('/api/rede/sincronizar', { body: {} }); S.entrou = true; ir('descarregar'); } catch (e) { alerta('Erro de Sincronização', e.message); } };
  // atualiza lista de auxiliares / lider detectado sem perder o formulario
  iniciarPoll(async () => { if (S.view !== 'home' || document.activeElement.tagName === 'INPUT') return;
    const n = await api('/api/state'); const chave = JSON.stringify([n.rede.lider, n.rede.auxiliares.length, n.servir_finalizado_remotamente]);
    if (S.chave !== undefined && S.chave !== chave) { const fm = S.form; ler(); render(); } S.chave = chave; }, 3000);
}

// ---------- DESCARREGAMENTO (assistente passo a passo) ----------
const PASSOS = ['Origem', 'Fotógrafo', 'Destino', 'Copiando', 'Finalizar'];
async function vDescarregar() {
  const st = S.st, sv = st.active_servir;
  S.entrou = true; S.avulso = !sv;
  const W = S.wiz || (S.wiz = { step: 1, pastas: [] });
  const tr = await api('/api/transferencia/status');
  if (tr.estado === 'rodando') W.step = 4;
  else if (tr.estado === 'concluido' || st.transferidas > 0) W.step = 5;
  else if (W.step >= 4) W.step = sv ? 2 : 3;
  if (sv && W.step === 3) W.step = 2;
  const nP = k => (sv && k > 3 ? k - 1 : k);   // numero exibido do passo

  // opcoes de destino local e de Drive
  const optsDest = []; if (sv && sv.local_path) optsDest.push({ r: 'Pasta do Servir: ' + (sv.local_nome || sv.local_path), p: sv.local_path });
  optsDest.push({ r: 'Pasta do Aplicativo (Padrão)', p: st.destino_padrao });
  st.pastas_local.forEach(p => optsDest.push({ r: p.nome, p: p.caminho }));
  if (!S.sel.destR || !optsDest.concat([{ r: 'Escolher pasta personalizada...' }]).some(o => o.r === S.sel.destR)) { S.sel.destR = optsDest[0].r; S.sel.destP = optsDest[0].p; }
  if (sv) { S.sel.destR = optsDest[0].r; S.sel.destP = optsDest[0].p; }
  const optsDrive = []; const dfs = sv ? (sv.drive_folders && sv.drive_folders.length ? sv.drive_folders : (sv.drive_link ? [{ link: sv.drive_link, nome: sv.drive_nome || 'Configurada' }] : [])) : [];
  dfs.forEach(d => optsDrive.push({ r: 'Pasta do Servir: ' + d.nome, l: d.link }));
  optsDrive.push({ r: 'Raiz do Google Drive (Padrão)', l: '' }); st.pastas_drive.forEach(p => optsDrive.push({ r: p.nome, l: p.link }));
  if (!S.sel.drive || !optsDrive.some(o => o.r === S.sel.drive)) S.sel.drive = optsDrive[0].r;
  if (sv && W.step === 5 && !S.sel.driveManual && S.sel.cat && S.sel.cat !== 'Raiz (Nenhuma)') {   // sugere a pasta do Drive da categoria usada
    const sug = optsDrive.map(o => o.r).filter(r => r.startsWith(`Pasta do Servir: ${S.sel.cat} `)).sort().pop(); if (sug) S.sel.drive = sug;
  }
  const cats = sv ? [...(sv.pastas_predefinidas || []), 'Raiz (Nenhuma)'] : [];
  if (sv) { if (!cats.includes(S.sel.cat)) S.sel.cat = cats[0]; if (!sv.voluntarios.includes(S.sel.fot) && S.sel.fot !== 'Outro...') S.sel.fot = sv.voluntarios[0]; }
  if (S.sel.sub === undefined) S.sel.sub = true;

  const nomeFot = () => (sv ? (S.sel.fot === 'Outro...' ? (S.sel.outro || '') : S.sel.fot) : (S.sel.nome || '')).trim();
  const nomeOk = () => { const n = nomeFot(); return n && !/[\\/:*?"<>|]/.test(n) && n !== '.' && n !== '..'; };
  const catAtual = () => sv ? S.sel.cat : 'Raiz (Nenhuma)';
  const subpasta = () => sv ? true : !!S.sel.sub;
  const resumoOrigem = () => `💾 ${esc(S.oCam || '')} · ${W.pastas.length} pasta(s) selecionada(s)`;

  // --- cabecalho + indicador de passos ---
  const passosVis = sv ? PASSOS.filter((_, i) => i !== 2) : PASSOS, atual = nP(W.step);
  const stepper = `<div class="stepper">${passosVis.map((n, i) => { const k = i + 1; return `<div class="stp ${k < atual ? 'done' : k === atual ? 'cur' : ''}"><span>${k < atual ? '✓' : k}</span><small>${n}</small></div>`; }).join('<i></i>')}</div>`;
  const resumos = [];
  if (W.step > 1) resumos.push({ k: 1, t: resumoOrigem() });
  if (W.step > 2) resumos.push({ k: 2, t: `👤 <b>${esc(nomeFot())}</b>${sv ? ' · 📂 ' + esc(catAtual()) : ''}` });
  if (W.step > 3) resumos.push({ k: 3, t: `📁 <span class="mini">${esc(S.finalPath || S.sel.destP)}</span>` });
  const editavel = W.step <= 3;

  let corpo = '';
  if (W.step === 1) corpo = `<h2>Passo 1 · De onde vêm as fotos?</h2><p class="mut">Insira o cartão SD no computador. Ele é detectado automaticamente.</p>
    <div id="o-status"></div><div class="checks" id="o-lista" style="margin-top:8px"></div>
    <div class="row" style="margin-top:8px"><button class="cinza" id="o-man">📂 Escolher outra pasta de origem</button><button class="cinza fix" id="o-open">Abrir cartão</button></div><div id="o-cand" class="chips"></div>
    <div class="nav"><span></span><button class="verde" id="w-next" disabled>Continuar ➜</button></div>`;
  else if (W.step === 2) corpo = `<h2>Passo 2 · Quem está descarregando?</h2>
    ${sv ? `<label>Fotógrafo (voluntário)</label><select id="s-fot">${sv.voluntarios.map(v => `<option ${S.sel.fot === v ? 'selected' : ''}>${esc(v)}</option>`).join('')}<option ${S.sel.fot === 'Outro...' ? 'selected' : ''}>Outro...</option></select>
      <input type="text" id="s-outro" placeholder="Digite o nome do fotógrafo" value="${esc(S.sel.outro || '')}" class="${S.sel.fot === 'Outro...' ? '' : 'hidden'}" style="margin-top:6px">
      <label>Em qual categoria salvar?</label><select id="s-cat">${cats.map(c => `<option ${S.sel.cat === c ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select>`
      : `<label>Nome do fotógrafo</label><input type="text" id="s-nome" value="${esc(S.sel.nome || '')}" placeholder="Digite o nome do fotógrafo">
      <label style="font-weight:400;display:flex;gap:8px;align-items:center"><input type="checkbox" id="s-sub" ${S.sel.sub ? 'checked' : ''}> Criar subpasta com o nome do fotógrafo</label>`}
    ${sv ? '<label>As fotos serão salvas em</label><div class="path" id="s-final">…</div>' : ''}
    <p id="s-erro" class="bad mini"></p>
    <div class="nav"><button class="cinza" id="w-back">⬅ Voltar</button><button class="verde" id="w-next">${sv ? '▶ Iniciar Descarregamento' : 'Continuar ➜'}</button></div>`;
  else if (W.step === 3) corpo = `<h2>Passo 3 · Onde salvar no computador?</h2>
    <select id="s-dest">${optsDest.map(o => `<option ${S.sel.destR === o.r ? 'selected' : ''}>${esc(o.r)}</option>`).join('')}<option ${S.sel.destR === 'Escolher pasta personalizada...' ? 'selected' : ''}>Escolher pasta personalizada...</option></select>
    <label>As fotos serão salvas em</label><div class="path" id="s-final">…</div>
    <div class="nav"><button class="cinza" id="w-back">⬅ Voltar</button><button class="verde" id="b-iniciar">▶ Iniciar Descarregamento</button></div>`;
  else if (W.step === 4) corpo = `<h2>Passo ${nP(4)} · Copiando fotos…</h2><p class="mut">Não feche esta página nem remova o cartão até terminar.</p>
    <progress id="pg" value="${tr.progresso || 0}" max="1"></progress><div id="pg-t" class="mut" style="margin-top:6px">${esc(tr.msg || '')}</div>`;
  else corpo = `<h2 class="ok">✅ Passo ${nP(5)} · Descarregamento concluído!</h2><p class="mut">${esc(tr.msg || '')}${st.transferidas ? ` · ${st.transferidas} foto(s) disponíveis para revisão` : ''}</p>
    <button class="grande" id="b-sel" ${st.transferidas ? '' : 'disabled'}>🖼️ Selecionar Fotos (apagar as ruins)</button>
    ${st.editor_disponivel ? `<button class="grande roxo" id="b-edit" style="margin-top:8px" ${st.transferidas ? '' : 'disabled'}>🎨 Editar Fotos (luz e cor)</button>` : ''}
    <div class="row" style="margin-top:8px"><button class="cinza" id="b-abrir">📁 Abrir Pasta</button><button class="cinza" id="b-novo">🔄 Novo Descarregamento</button></div>
    <h3>☁️ Enviar para o Google Drive (opcional)</h3><select id="s-drive">${optsDrive.map(o => `<option ${S.sel.drive === o.r ? 'selected' : ''}>${esc(o.r)}</option>`).join('')}</select>
    <button class="lar" id="b-up" style="margin-top:8px;width:100%" ${st.transferidas ? '' : 'disabled'}>⬆ Enviar fotos para o Drive</button>
    <p class="mut mini">O envio roda em segundo plano — você já pode iniciar um novo descarregamento. O progresso aparece no canto superior direito.</p>`;

  $app.innerHTML = `<div class="wrap" style="max-width:760px">
  <div class="topbar"><div><h1>${sv ? '🙏 ' + esc(sv.nome) : '📂 Modo Avulso'}</h1><div class="mut mini">${sv ? 'Dia do Servir ativo' : 'Sem dia de servir'}</div></div>
   <div class="acts">${sv && st.rede.modo === 'lider' ? '<button class="pq" id="b-qr">📱 Painel (QR)</button>' : ''}${sv ? '<button class="lar pq" id="b-raiz">📁 Pasta do Servir</button><button class="verm pq" id="b-fin">🏁 Finalizar Servir</button>' : ''}<button class="cinza pq" id="b-voltar">⬅ Início</button></div></div>
  ${stepper}
  ${resumos.map(r => `<div class="resumo"><span>${r.t}</span>${editavel ? `<button class="pq cinza" data-ed="${r.k}">Alterar</button>` : ''}</div>`).join('')}
  <div class="card passo">${corpo}</div></div>`;

  const q = s => $app.querySelector(s);
  q('#b-voltar').onclick = async () => { await api('/api/avulso', { body: {} }); S.entrou = false; S.avulso = false; S.wiz = null; ir('home'); };
  if (sv) {
    q('#b-raiz').onclick = () => api('/api/fs/abrir', { body: { path: S.sel.destP + '/' + sv.nome } }).catch(() => alerta('Informação', `A pasta raiz do servir '${sv.nome}' ainda não foi criada localmente.`));
    q('#b-fin').onclick = () => finalizarServir();
    if (st.rede.modo === 'lider') { q('#b-qr').onclick = mostrarQR; if (S.qr) { S.qr = false; mostrarQR(); } }
  }
  S.qr = false;
  $app.querySelectorAll('[data-ed]').forEach(b => b.onclick = () => { W.step = +b.dataset.ed; vDescarregar(); });
  const ir_ = n => { W.step = n; vDescarregar(); };

  async function atualizaFinal() {
    const el = q('#s-final'); if (!el) return;
    if (!S.sel.destP) { el.textContent = 'Selecione a pasta de destino acima...'; return; }
    try { const d = await api(`/api/destino/preview?base=${encodeURIComponent(S.sel.destP)}&fotografo=${encodeURIComponent(nomeFot())}&categoria=${encodeURIComponent(catAtual())}&subpasta=${subpasta()}`); S.finalPath = d.caminho; el.textContent = d.caminho; } catch (e) { }
  }
  async function iniciar() {
      const body = { fotografo: nomeFot(), destino_base: S.sel.destP, pastas: W.pastas, categoria: catAtual(), subpasta: subpasta() };
      try {
        const plano = await api('/api/transferencia/plano', { body });
        if (plano.total_encontrados === 0) return alerta('Informação', 'Nenhuma imagem encontrada nas pastas selecionadas.');
        let modo = 'novas';
        if (plano.novas === 0 && plano.ja_descarregados > 0) {
          if (!await confirmar('Fotos Já Descarregadas', `Atenção: Todas as ${plano.ja_descarregados} fotos encontradas já foram descarregadas anteriormente!\n\nDeseja descarregá-las novamente?`)) return;
          modo = 'todas';
        } else if (plano.novas > 0 && plano.ja_descarregados > 0) {
          if (!await confirmar('Fotos Já Descarregadas', `Atenção: Foram detectadas ${plano.ja_descarregados} fotos já descarregadas anteriormente nesta pasta.\n\nDeseja descarregar apenas as ${plano.novas} novas fotos tiradas após o último descarregamento?\n(Se selecionar 'Não', todas as ${plano.todas} fotos serão copiadas).`)) modo = 'todas';
        }
        const temRaw = modo === 'novas' ? plano.tem_raw_novas : plano.tem_raw;
        let converter_raw = false;
        if (temRaw && plano.pode_converter_raw) {
          const r = await modal(`<h2>Fotos em RAW Detectadas</h2>${esc('Tem fotos em RAW (.cr3, .cr2, .nef, .arw) no meio das selecionadas.\n\nDeseja transformar RAW em JPEG?\n\nOs JPEGs saem na resolução total. No computador fica só o JPEG (o RAW copiado é apagado depois de convertido). O cartão não é alterado.')}`,
            [{ t: 'Cancelar', v: null, c: 'cinza' }, { t: 'Manter em RAW', v: false, c: 'cinza' }, { t: 'Transformar em JPEG', v: true }]);
          if (r === null) return;
          converter_raw = r;
        } else if (temRaw && !await confirmar('Fotos em RAW Detectadas', 'Atenção: Foram detectadas fotos em formato RAW (.cr3, .cr2, .nef, .arw) nas pastas selecionadas.\n\nElas serão copiadas no formato original. Deseja prosseguir com o descarregamento?')) return;
        await api('/api/transferencia/iniciar', { body: { ...body, modo, converter_raw } });
        ir_(4);
      } catch (e) { toast(e.message, true); }
  }

  // ---- passo 1 ----
  if (W.step === 1) {
    const marcarProx = () => { W.pastas = [...document.querySelectorAll('#o-lista input:checked')].map(i => i.value); q('#w-next').disabled = !(S.oOk && W.pastas.length); };
    async function atualizaOrigem() {
      if (S.view !== 'descarregar' || W.step !== 1 || !q('#o-status')) return;
      const o = await api('/api/origem'); S.oOk = o.detectada; S.oCam = o.caminho;
      const chave = JSON.stringify([o.caminho, o.detectada, o.pastas.length, o.candidatos]);
      if (S.oChave !== chave) {
        S.oChave = chave;
        q('#o-status').innerHTML = o.detectada ? `<span class="${o.manual ? 'az' : 'ok'}">${o.manual ? 'Origem manual' : '✅ Cartão detectado'}: ${esc(o.caminho)}</span>` : '<span class="warn">⏳ Aguardando inserção do Cartão SD...</span>';
        const marc = new Set(W.pastas);
        q('#o-lista').innerHTML = o.detectada ? o.pastas.map(p => `<label><input type="checkbox" value="${esc(p.valor)}" ${marc.has(p.valor) ? 'checked' : ''}> ${esc(p.rotulo)}</label>`).join('') : '<p class="mut">Nenhum cartão detectado.</p>';
        q('#o-lista').querySelectorAll('input').forEach(i => i.onchange = marcarProx);
        q('#o-cand').innerHTML = o.candidatos.map((c, i) => `<span class="chip" style="cursor:pointer" data-c="${i}">💾 ${esc(c.mountpoint)}</span>`).join('');
        q('#o-cand').querySelectorAll('[data-c]').forEach(e => e.onclick = async () => { await api('/api/origem', { body: { path: o.candidatos[e.dataset.c].mountpoint } }); S.oChave = null; W.pastas = []; atualizaOrigem(); });
      }
      marcarProx();
    }
    S.oChave = null; await atualizaOrigem();
    q('#o-man').onclick = async () => { const p = await escolherPasta('Selecione a pasta de origem das fotos (cartão ou pasta)', S.oUlt); if (p) { S.oUlt = p; try { await api('/api/origem', { body: { path: p } }); S.oChave = null; W.pastas = []; atualizaOrigem(); } catch (e) { toast(e.message, true); } } };
    q('#o-open').onclick = async () => { const o = await api('/api/origem'); if (o.caminho) api('/api/fs/abrir', { body: { path: o.caminho } }).catch(e => toast(e.message, true)); };
    q('#w-next').onclick = () => { avisarAtividade(); ir_(2); };
    iniciarPoll(atualizaOrigem, 2000);
  }
  // ---- passo 2 ----
  if (W.step === 2) {
    if (sv) {
      avisarAtividade(nomeFot());
      q('#s-fot').onchange = e => { S.sel.fot = e.target.value; if (e.target.value !== 'Outro...') avisarAtividade(nomeFot()); q('#s-outro').classList.toggle('hidden', e.target.value !== 'Outro...'); if (e.target.value === 'Outro...') q('#s-outro').focus(); atualizaFinal(); };
      q('#s-outro').oninput = e => { S.sel.outro = e.target.value; atualizaFinal(); };
      q('#s-cat').onchange = e => { S.sel.cat = e.target.value; atualizaFinal(); };
    } else { q('#s-nome').oninput = e => { S.sel.nome = e.target.value; }; q('#s-sub').onchange = e => { S.sel.sub = e.target.checked; }; q('#s-nome').focus(); }
    const avancar = () => { if (!nomeOk()) { q('#s-erro').textContent = nomeFot() ? 'O nome não pode conter / \\ : * ? " < > |' : 'Selecione ou digite o nome do fotógrafo.'; return; } avisarAtividade(nomeFot()); if (sv) iniciar(); else ir_(3); };
    q('#w-next').onclick = avancar; q('#w-back').onclick = () => ir_(1);
    $app.querySelectorAll('input[type=text]').forEach(i => i.onkeydown = e => { if (e.key === 'Enter') avancar(); });
    if (sv) atualizaFinal();
  }
  // ---- passo 3 ----
  if (W.step === 3) {
    await atualizaFinal();
    q('#w-back').onclick = () => ir_(2);
    q('#s-dest').onchange = async e => {
      const v = e.target.value;
      if (v === 'Escolher pasta personalizada...') { const p = await escolherPasta('Selecione onde salvar as fotos', S.sel.destP); if (p) { S.sel.destR = v; S.sel.destP = p; } else e.target.value = S.sel.destR; }
      else { const o = optsDest.find(x => x.r === v); S.sel.destR = v; S.sel.destP = o.p; }
      atualizaFinal();
    };
    q('#b-iniciar').onclick = iniciar;
  }
  // ---- passo 4 ----
  if (W.step === 4) {
    iniciarPoll(async () => {
      const t = await api('/api/transferencia/status'); const pg = q('#pg'); if (!pg) return;
      pg.value = t.progresso; q('#pg-t').textContent = `${t.fase === 'convertendo' ? 'Convertendo RAW para JPEG · ' : ''}${Math.round(t.progresso * 100)}% (${t.feitos}/${t.total})`;
      if (t.estado === 'concluido' || t.estado === 'erro') {
        pararPoll();
        if (t.estado === 'erro') { await alerta('Erro', t.msg); W.step = 3; return vDescarregar(); }
        if (t.aviso) await alerta('Atenção', t.aviso);
        W.step = 5; await render();
        if (t.revisaveis > 0 && await confirmar('Transferência Finalizada', `Foram transferidas ${t.revisaveis} foto(s) com sucesso!${t.falhas ? `\n(${t.falhas} arquivo(s) com erro de cópia — veja o log do servidor.)` : ''}${t.falhas_raw ? `\n(${t.falhas_raw} RAW não puderam ser convertidos e ficaram em RAW — veja o log do servidor.)` : ''}\n\nDeseja iniciar a tela de seleção agora para revisar e apagar as fotos indesejadas?`)) abrirRevisor();
        else if (t.revisaveis === 0) alerta('Concluído', 'A cópia foi finalizada, mas nenhuma imagem compatível com revisão foi transferida.');
      }
    }, 600);
  }
  // ---- passo 5 ----
  if (W.step === 5) {
    q('#b-sel').onclick = abrirRevisor;
    if (q('#b-edit')) q('#b-edit').onclick = () => abrirEditor();
    q('#b-abrir').onclick = () => api('/api/revisor/abrir-pasta', { body: {} }).catch(e => toast(e.message, true));
    q('#b-novo').onclick = async () => { await api('/api/transferencia/nova', { body: {} }); S.sel.nome = ''; S.sel.outro = ''; S.sel.driveManual = false; W.step = 1; W.pastas = []; S.oChave = null; await carregar(); vDescarregar(); };
    q('#s-drive').onchange = e => { S.sel.drive = e.target.value; S.sel.driveManual = true; };
    q('#b-up').onclick = async ev => {
      const btn = ev.currentTarget; if (btn.disabled) return;
      btn.disabled = true;   // duplo clique nao envia duas vezes
      const o = optsDrive.find(x => x.r === S.sel.drive);
      try {
        const r = await api('/api/upload/iniciar', { body: { link: o ? o.l : '' } });
        toast(r && r.ignoradas ? `Envio iniciado (${r.ignoradas} foto(s) já enviadas ou em envio foram puladas).` : 'Envio ao Drive iniciado em segundo plano.');
        uploadsAtualiza();
      } catch (e) { alerta('Upload', e.message); }
      setTimeout(() => { btn.disabled = false; }, 1500);
    };
  }
}

async function finalizarServir(ignorar) {
  if (!ignorar && !await confirmar('Finalizar Servir', 'Tem certeza que deseja finalizar este Servir e enviar todos os dados para o webhook?')) return;
  const b = document.getElementById('b-fin'); if (b) { b.disabled = true; b.textContent = 'Enviando...'; }
  try {
    const r = await api('/api/servir/finalizar', { body: { ignorar_erros: !!ignorar } });
    if (r.status === 'confirmar') {
      if (b) { b.disabled = false; b.textContent = '🏁 Finalizar Servir'; }
      if (await confirmar('Erro de Comunicação LAN', `Não foi possível obter dados das seguintes estações:\n${r.estacoes_com_erro.join(', ')}\n\nDeseja finalizar o Servir mesmo assim (ignorando estas estações)?`)) return finalizarServir(true);
      return;
    }
    await alerta('Sucesso', 'Servir finalizado com sucesso! Todos os dados foram enviados para o webhook.'); S.entrou = false; S.wiz = null; ir('home');
  } catch (e) { if (b) { b.disabled = false; b.textContent = '🏁 Finalizar Servir'; } alerta('Erro ao Finalizar', 'Não foi possível enviar os dados ao webhook:\n' + e.message); }
}

// ---------- zoom da tela de selecao ----------
// Roda do mouse / pinca no ponto do cursor, arrastar para mover, duplo clique alterna entre "tela inteira" e 100%.
// Quando a foto aparece maior que a imagem carregada (zoom ou tela grande), busca a foto no tamanho original.
// O zoom e a posicao continuam ao trocar de foto: da para conferir o foco da mesma regiao numa sequencia.
function criarZoom(stage, img, aoMudar) {
  const Z = { z: 1, cx: .5, cy: .5, urlOrig: '', alta: false, origW: 0, carregando: false, cem: null };
  let fitW = 0, fitH = 0, sw = 0, sh = 0, ptrs = new Map(), gesto = null;
  const selo = document.createElement('div'); selo.className = 'zselo hidden'; stage.appendChild(selo);
  function medidas() {
    sw = stage.clientWidth; sh = stage.clientHeight;
    const ar = (img.naturalWidth || 3) / (img.naturalHeight || 2);
    fitW = Math.min(sw, sh * ar); fitH = fitW / ar;
  }
  const maxZ = () => Math.max(2, Z.origW ? 4 * Z.origW / fitW : 8);   // ate 400% do original
  const pos = () => ({ w: fitW * Z.z, h: fitH * Z.z, l: sw / 2 - Z.cx * fitW * Z.z, t: sh / 2 - Z.cy * fitH * Z.z });
  function desenha() {
    if (!fitW) return;
    let { w, h, l, t } = pos();
    if (w <= sw) { l = (sw - w) / 2; Z.cx = .5; } else { l = Math.min(0, Math.max(sw - w, l)); Z.cx = (sw / 2 - l) / w; }
    if (h <= sh) { t = (sh - h) / 2; Z.cy = .5; } else { t = Math.min(0, Math.max(sh - h, t)); Z.cy = (sh / 2 - t) / h; }
    Object.assign(img.style, { width: w + 'px', height: h + 'px', left: l + 'px', top: t + 'px' });
    stage.classList.toggle('zoom', Z.z > 1.01);
    if (!Z.alta && w > img.naturalWidth * 1.15) carregarOriginal();
    aoMudar(Z.z <= 1.01 ? 'Tela inteira' : Z.origW ? Math.round(w / Z.origW * 100) + '%' : Z.z.toFixed(1) + '×');
  }
  function zoomEm(novo, mx, my) {
    const a = pos(), px = (mx - a.l) / a.w, py = (my - a.t) / a.h;
    Z.z = Math.min(maxZ(), Math.max(1, novo));
    const w = fitW * Z.z, h = fitH * Z.z;
    Z.cx = (sw / 2 - (mx - px * w)) / w; Z.cy = (sh / 2 - (my - py * h)) / h;
    desenha();
  }
  function carregarOriginal() {
    if (Z.carregando || !Z.urlOrig) return;
    Z.carregando = true; const url = Z.urlOrig, im = new Image();
    const t = setTimeout(() => { if (Z.urlOrig === url) selo.classList.remove('hidden'); }, 300);
    selo.textContent = 'Carregando em alta resolução…';
    im.onload = () => {
      clearTimeout(t); selo.classList.add('hidden'); Z.carregando = false;
      if (Z.urlOrig !== url) return desenha();             // ja trocou de foto: busca a original da atual, se precisar
      Z.alta = true; Z.origW = im.naturalWidth; img.src = url;
      if (Z.cem) { const c = Z.cem; Z.cem = null; zoomEm(Z.origW / fitW, c.x, c.y); } else desenha();
    };
    im.onerror = () => { clearTimeout(t); Z.carregando = false; if (Z.urlOrig !== url) return desenha(); selo.textContent = 'Não foi possível carregar em alta resolução'; selo.classList.remove('hidden'); };
    im.src = url;
  }
  const centro = () => ({ x: sw / 2, y: sh / 2 });
  const ajustar = () => { Z.z = 1; Z.cx = Z.cy = .5; Z.cem = null; desenha(); };
  function cem(p = centro()) {                             // 100%: um pixel da foto = um pixel da tela
    if (Z.origW) zoomEm(Z.origW / fitW, p.x, p.y);
    else { Z.cem = p; zoomEm(Math.max(Z.z, 2), p.x, p.y); carregarOriginal(); }
  }
  const local = e => { const r = stage.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  stage.addEventListener('wheel', e => { e.preventDefault(); const p = local(e); zoomEm(Z.z * Math.exp(-e.deltaY * 0.0015), p.x, p.y); }, { passive: false });
  stage.addEventListener('dblclick', e => { if (Z.z > 1.01) ajustar(); else cem(local(e)); });
  stage.addEventListener('pointerdown', e => {
    stage.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, local(e));
    const ps = [...ptrs.values()];
    if (ps.length === 2) gesto = { tipo: 'pinca', d: Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y), z: Z.z };
    else if (Z.z > 1.01) { gesto = { tipo: 'mover', ...local(e), cx: Z.cx, cy: Z.cy }; stage.classList.add('arrastando'); }
  });
  stage.addEventListener('pointermove', e => {
    if (!ptrs.has(e.pointerId) || !gesto) return;
    ptrs.set(e.pointerId, local(e));
    const ps = [...ptrs.values()];
    if (gesto.tipo === 'pinca' && ps.length === 2) {
      const d = Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y);
      zoomEm(gesto.z * d / gesto.d, (ps[0].x + ps[1].x) / 2, (ps[0].y + ps[1].y) / 2);
    } else if (gesto.tipo === 'mover') {
      const p = local(e); Z.cx = gesto.cx - (p.x - gesto.x) / (fitW * Z.z); Z.cy = gesto.cy - (p.y - gesto.y) / (fitH * Z.z); desenha();
    }
  });
  const solta = e => { ptrs.delete(e.pointerId); if (ptrs.size < 2 && gesto && gesto.tipo === 'pinca') gesto = null; if (!ptrs.size) { gesto = null; stage.classList.remove('arrastando'); } };
  stage.addEventListener('pointerup', solta); stage.addEventListener('pointercancel', solta);
  img.draggable = false;
  img.addEventListener('load', () => { medidas(); desenha(); });
  const redimensiona = () => { medidas(); desenha(); };
  addEventListener('resize', redimensiona);
  return {
    // nova foto: mostra a versao leve; a original vem sozinha se o zoom (que continua) precisar
    foto(urlLeve, urlOrig) { Z.urlOrig = urlOrig; Z.alta = false; Z.origW = 0; Z.cem = null; selo.classList.add('hidden'); img.src = urlLeve; },
    mais: () => zoomEm(Z.z * 1.5, centro().x, centro().y),
    menos: () => zoomEm(Z.z / 1.5, centro().x, centro().y),
    alternar: () => (Z.z > 1.01 ? ajustar() : cem()),
    ajustar, cem: () => cem(),
    precisaOriginal: () => Z.z > 1.01,
    destruir: () => removeEventListener('resize', redimensiona),
  };
}

// ---------- EDITOR DE FOTOS (Luz, Curva e Cor; motor do LightCraft, como no app LightCraft) ----------
// A previa e revelada pelo proprio LightCraft (o que aparece e o que vai para o Drive). Ao trocar de foto ou concluir,
// a foto editada e salva em tamanho cheio em segundo plano; a original fica guardada (botao "Restaurar original").
const ED_SECOES = [['luz', 'Luz'], ['curva', 'Curva de tons'], ['cor', 'Cor']];
const ED_TRILHO = { 'wb.temp': 'trk-temp', 'wb.tint': 'trk-tint', 'color.vibrance': 'trk-vib', 'color.saturation': 'trk-sat' };
const T_MIN = Math.log(2000), T_MAX = Math.log(50000);           // temperatura em escala logaritmica (mais facil de ajustar)
const tPos = t => Math.round((Math.log(t) - T_MIN) / (T_MAX - T_MIN) * 1000), tVal = p => Math.round(Math.exp(T_MIN + p / 1000 * (T_MAX - T_MIN)) / 50) * 50;
async function abrirEditor(inicio = 0) {
  let info; try { info = await api('/api/editor'); } catch (e) { return toast(e.message, true); }
  if (!info.disponivel) return alerta('Editor indisponível', 'O motor de edição (LightCraft) não está instalado neste computador.');
  if (!info.fotos.length) return alerta('Aviso', 'Não há fotos para editar.');
  pararPoll();
  const C = info.controles, v = Date.now(), fechadas = new Set(['curva']);
  let fotos = info.fotos, i = Math.min(inicio, fotos.length - 1), aj = null, salvo = '', cf = { temp: 6500, tint: 0 };
  let antes = false, conta = false, emVoo = false, deNovo = false, urlBlob = null, versaoMini = {};
  const el = document.createElement('div'); el.className = 'rev ed';
  el.innerHTML = `<div class="bar"><button class="cinza" id="e-ant">◀ Anterior</button><div class="info" id="e-info"></div><button class="cinza" id="e-prox">Próxima ▶</button>
    <button class="cinza" id="e-antes" title="Ver a foto sem os ajustes (tecla \\)">Antes / Depois</button><button class="cinza" id="e-zerar" title="Zera todos os ajustes desta foto">Redefinir</button>
    <button class="cinza" id="e-rest" title="Volta a foto original guardada">Restaurar original</button><button class="verde" id="e-fim">✅ Concluir</button></div>
    <div class="ed-corpo"><div class="ed-foto" id="e-stage"><img id="e-img" alt="" draggable="false"><div class="zselo hidden" id="e-selo"></div><div class="ed-antes hidden" id="e-tag">Antes</div></div>
    <div class="ed-painel" id="e-painel"></div></div>
    <div class="strip" id="e-strip"></div><div class="kbd">← → trocar de foto · \\ antes/depois · W conta-gotas · duplo clique numa régua: volta ao padrão · Esc concluir</div>`;
  document.body.appendChild(el);
  const $ = s => el.querySelector(s), img = $('#e-img'), stage = $('#e-stage'), selo = $('#e-selo');
  const aviso = t => { selo.textContent = t; selo.classList.toggle('hidden', !t); };
  const fmt = (c, x) => c === 'wb.temp' ? String(Math.round(x)) : (x > 0 ? '+' : '') + x.toFixed(C[c].passo < 1 ? 2 : 0).replace('.', ',');
  const valor = c => c === 'wb.temp' ? aj.wb.temp : c === 'wb.tint' ? aj.wb.tint : aj.valores[c];

  // --- painel ---
  function painel() {
    $('#e-painel').innerHTML = ED_SECOES.map(([s, nome]) => `<button class="ed-sec" data-s="${s}">${fechadas.has(s) ? '▸' : '▾'} ${nome}</button>
      <div class="ed-grupo ${fechadas.has(s) ? 'hidden' : ''}">${s === 'cor' ? `<div class="ed-wb"><span>Equilíbrio de branco</span><select id="e-wb">${Object.entries(info.modos_wb).map(([m, r]) => `<option value="${m}">${esc(r)}</option>`).join('')}</select><button class="cinza" id="e-pick" title="Conta-gotas: clique num ponto que deveria ser cinza/branco (W)">🎯</button></div>` : ''}
      ${Object.keys(C).filter(c => C[c].secao === s).map(c => `<div class="ed-ctl" data-c="${c}" title="Duplo clique: volta ao padrão"><div class="ed-lin"><span>${esc(C[c].rotulo)}</span><span class="ed-val"></span></div>
        <input type="range" class="${ED_TRILHO[c] || 'trk-centro'}" ${c === 'wb.temp' ? 'min="0" max="1000" step="1"' : `min="${C[c].min}" max="${C[c].max}" step="${C[c].passo}"`}></div>`).join('')}</div>`).join('');
    $('#e-painel').querySelectorAll('.ed-sec').forEach(b => b.onclick = () => { const s = b.dataset.s; fechadas.has(s) ? fechadas.delete(s) : fechadas.add(s); painel(); mostraValores(); });
    $('#e-painel').querySelectorAll('.ed-ctl').forEach(d => {
      const c = d.dataset.c, r = d.querySelector('input');
      r.oninput = () => {
        if (!aj) return;
        const x = c === 'wb.temp' ? tVal(+r.value) : +r.value;
        if (c === 'wb.temp' || c === 'wb.tint') { aj.wb[c === 'wb.temp' ? 'temp' : 'tint'] = x; aj.wb.modo = 'custom'; } else aj.valores[c] = x;
        mostraValores(); agendar();
      };
      d.ondblclick = () => {                                   // como no Lightroom: duplo clique zera
        if (!aj) return;
        if (c === 'wb.temp' || c === 'wb.tint') aj.wb = { modo: 'asShot', ...cf }; else aj.valores[c] = C[c].padrao;
        mostraValores(); agendar();
      };
    });
    $('#e-wb').onchange = async e => {
      const modo = e.target.value;
      if (modo === 'asShot') aj.wb = { modo, ...cf };
      else if (modo !== 'custom') { try { const r = await api(`/api/editor/${i}/balanco`, { body: { modo, ajustes: aj } }); aj.wb = { modo, temp: r.temp, tint: r.tint }; } catch (er) { toast(er.message, true); } }
      else aj.wb.modo = 'custom';
      mostraValores(); agendar();
    };
    $('#e-pick').onclick = () => contaGotas(!conta);
  }
  function mostraValores() {
    $('#e-painel').querySelectorAll('.ed-ctl').forEach(d => {
      const c = d.dataset.c, x = valor(c), r = d.querySelector('input');
      r.value = c === 'wb.temp' ? tPos(x) : x; d.querySelector('.ed-val').textContent = fmt(c, x);
      d.classList.toggle('mudou', c.startsWith('wb.') ? aj.wb.modo !== 'asShot' : x !== C[c].padrao);
    });
    const s = $('#e-wb'); if (s) s.value = aj.wb.modo;
    const p = $('#e-pick'); if (p) p.classList.toggle('ativo', conta);
  }
  function contaGotas(ligar) { conta = ligar; stage.classList.toggle('pick', conta); aviso(conta ? 'Clique num ponto que deveria ser branco ou cinza' : ''); mostraValores(); }
  img.onclick = async e => {
    if (!conta) return;
    const r = img.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    contaGotas(false);
    try { const b = await api(`/api/editor/${i}/balanco`, { body: { x, y, ajustes: aj } }); aj.wb = { modo: 'custom', temp: b.temp, tint: b.tint }; mostraValores(); agendar(); }
    catch (er) { toast(er.message, true); }
  };

  // --- previa ao vivo (uma por vez; a ultima mudanca sempre e mostrada) ---
  const ajTexto = () => JSON.stringify({ valores: aj.valores, wb: aj.wb });
  function agendar() { if (emVoo) { deNovo = true; return; } pedir(); }
  async function pedir() {
    emVoo = true; deNovo = false;
    const alvo = i, lado = Math.min(2048, Math.round(Math.max(stage.clientWidth, stage.clientHeight) * (window.devicePixelRatio || 1)));
    const t = setTimeout(() => aviso('Revelando…'), 600);
    try {
      const r = await fetch(`/api/editor/${i}/previa?lado=${lado}&aj=${encodeURIComponent(antes ? '{}' : ajTexto())}`);
      if (!r.ok) throw new Error(((await r.json().catch(() => ({}))).detail) || 'Erro ' + r.status);
      const b = await r.blob();
      if (alvo === i) { const u = URL.createObjectURL(b); img.src = u; if (urlBlob) URL.revokeObjectURL(urlBlob); urlBlob = u; }
      clearTimeout(t); if (!conta) aviso('');
    } catch (e) { clearTimeout(t); aviso('Não foi possível revelar: ' + e.message); }
    emVoo = false; if (deNovo) pedir();
  }

  // --- fotos ---
  function tira() {
    $('#e-strip').innerHTML = fotos.map((f, k) => `<span class="tb ${k === i ? 'cur' : ''}" data-k="${k}"><img src="/api/revisor/imagem/${k}?lado=160&v=${v}${versaoMini[k] ? '&m=' + versaoMini[k] : ''}" loading="lazy" title="${esc(f.nome)}">
      ${f.estado === 'salvando' ? '<b class="bd">salvando…</b>' : f.estado.startsWith('erro') ? '<b class="bd err" title="' + esc(f.estado) + '">erro</b>' : f.editada ? '<b class="bd">✎</b>' : ''}</span>`).join('');
    $('#e-strip').querySelectorAll('.tb').forEach(t => t.onclick = () => ir(+t.dataset.k));
    const cur = $('#e-strip .tb.cur'); if (cur) cur.scrollIntoView({ block: 'nearest', inline: 'center' });
  }
  async function atualizaLista() {
    try {
      const d = await api('/api/editor'), antesL = fotos;
      d.fotos.forEach((f, k) => { if (antesL[k] && antesL[k].estado === 'salvando' && f.estado !== 'salvando') versaoMini[k] = Date.now(); });
      fotos = d.fotos; tira(); return d.pendentes;
    } catch (e) { return 0; }
  }
  function salvarSeMudou() {
    const atual = ajTexto(); if (atual === salvo) return;
    salvo = atual; fotos[i].estado = 'salvando';
    api(`/api/editor/${i}/salvar`, { body: { ajustes: aj } }).catch(e => toast('Não foi possível salvar: ' + e.message, true));
  }
  async function carregar() {
    $('#e-info').innerHTML = `<b>Foto ${i + 1}/${fotos.length}</b> · ${esc(fotos[i].nome)}`;
    img.src = `/api/revisor/imagem/${i}?v=${v}${versaoMini[i] ? '&m=' + versaoMini[i] : ''}`;   // aparece na hora; a previa do LightCraft vem em seguida
    tira();
    try {
      const d = await api(`/api/editor/${i}`); cf = d.como_fotografado;
      aj = { valores: { ...d.ajustes.valores }, wb: d.ajustes.wb.modo === 'custom' ? d.ajustes.wb : { modo: d.ajustes.wb.modo, ...cf } };
      if (aj.wb.modo !== 'asShot' && aj.wb.modo !== 'custom') { try { const r = await api(`/api/editor/${i}/balanco`, { body: { modo: aj.wb.modo, ajustes: aj } }); aj.wb = { modo: aj.wb.modo, temp: r.temp, tint: r.tint }; } catch (e) { } }
      Object.keys(C).forEach(c => { if (!c.startsWith('wb.') && aj.valores[c] === undefined) aj.valores[c] = C[c].padrao; });
      salvo = ajTexto(); $('#e-rest').disabled = !d.editada; mostraValores(); agendar();
    } catch (e) { aviso(e.message); }
  }
  function ir(k) { if (k < 0 || k >= fotos.length || k === i) return; salvarSeMudou(); i = k; antes = false; $('#e-tag').classList.add('hidden'); contaGotas(false); carregar(); }
  function alternarAntes() { antes = !antes; $('#e-tag').classList.toggle('hidden', !antes); agendar(); }
  const vigia = setInterval(async () => { if (fotos.some(f => f.estado === 'salvando')) await atualizaLista(); }, 1500);
  async function concluir() {
    salvarSeMudou(); clearInterval(vigia);
    let n = await atualizaLista();
    while (n > 0) { aviso(`Salvando ${n} foto(s) editada(s)…`); await new Promise(r => setTimeout(r, 800)); n = await atualizaLista(); }
    const erros = fotos.filter(f => f.estado.startsWith('erro'));
    document.removeEventListener('keydown', tecla); if (urlBlob) URL.revokeObjectURL(urlBlob); el.remove();
    if (erros.length) await alerta('Atenção', `${erros.length} foto(s) não puderam ser salvas e ficaram como estavam:\n${erros.map(f => f.nome).join(', ')}`);
    render();
  }
  function tecla(e) {
    if (document.querySelector('.modal-bg') || !document.body.contains(el)) return;
    const emControle = ['INPUT', 'SELECT'].includes(document.activeElement.tagName);
    if (e.key === 'Escape') { if (conta) contaGotas(false); else concluir(); }
    else if (!emControle && e.key === 'ArrowRight') ir(i + 1); else if (!emControle && e.key === 'ArrowLeft') ir(i - 1);
    else if (e.key === '\\') alternarAntes(); else if (e.key.toLowerCase() === 'w' && !emControle) contaGotas(!conta);
  }
  document.addEventListener('keydown', tecla);
  $('#e-ant').onclick = () => ir(i - 1); $('#e-prox').onclick = () => ir(i + 1); $('#e-antes').onclick = alternarAntes; $('#e-fim').onclick = concluir;
  $('#e-zerar').onclick = () => { aj = { valores: Object.fromEntries(Object.keys(C).filter(c => !c.startsWith('wb.')).map(c => [c, C[c].padrao])), wb: { modo: 'asShot', ...cf } }; mostraValores(); agendar(); };
  $('#e-rest').onclick = async () => {
    if (!await confirmar('Restaurar original', `Desfazer todas as edições de "${fotos[i].nome}" e voltar à foto original?`, 'Restaurar', 'Cancelar')) return;
    try { await api(`/api/editor/${i}/restaurar`, { body: {} }); versaoMini[i] = Date.now(); await atualizaLista(); carregar(); } catch (e) { toast(e.message, true); }
  };
  addEventListener('resize', () => { if (document.body.contains(el)) agendar(); });
  painel(); carregar();
}

// ---------- REVISOR (selecao de fotos) ----------
async function abrirRevisor() {
  let lista; try { lista = (await api('/api/revisor')).arquivos; } catch (e) { return toast(e.message, true); }
  if (!lista.length) return alerta('Aviso', 'Não há fotos na lista de transferência para revisar.');
  pararPoll();
  const v = Date.now();   // muda a cada abertura: a URL so tem o indice, entao sem isso o navegador reaproveita fotos de descarregamentos anteriores
  const desc = new Set(); const ordemDesc = []; let i = 0; let tempo = null;
  const el = document.createElement('div'); el.className = 'rev';
  el.innerHTML = `<div class="bar"><button class="cinza" id="r-ant">◀ Anterior</button><div class="info" id="r-info"></div><button class="cinza" id="r-prox">Próxima ▶</button>
    <span class="zgrupo"><button class="cinza" id="r-zm" title="Diminuir zoom (−)">−</button><button class="cinza" id="r-zt" title="Alternar entre tela inteira e 100% (duplo clique na foto)">Tela inteira</button><button class="cinza" id="r-zp" title="Aumentar zoom (+)">+</button></span>
    <button class="verm" id="r-desc">🗑 Descartar (Del)</button><button class="cinza" id="r-undo">↩ Desfazer (Ctrl+Z)</button><button class="verde" id="r-fim">✅ Finalizar Seleção</button><button class="cinza" id="r-sair">✕</button></div>
    <div class="stage" id="r-stage"><img id="r-img" alt=""><div class="stamp hidden" id="r-stamp">DESCARTADA</div></div>
    <div class="strip" id="r-strip"></div><div class="kbd">← → navegar · Del/Backspace/X descartar · Ctrl+Z desfazer · Enter finalizar · Esc sair<br>Zoom: roda do mouse ou pinça · arrastar move · duplo clique ou 1 = 100% · + − · 0 = tela inteira</div>`;
  document.body.appendChild(el);
  const $ = s => el.querySelector(s); const img = $('#r-img');
  const zoom = criarZoom($('#r-stage'), img, t => { $('#r-zt').textContent = t; });
  $('#r-strip').innerHTML = lista.map((n, k) => `<img data-k="${k}" title="${esc(n)}" loading="lazy" src="/api/revisor/imagem/${k}?lado=160&v=${v}">`).join('');
  $('#r-strip').querySelectorAll('img').forEach(t => t.onclick = () => { i = +t.dataset.k; mostra(); });
  // com zoom, as proximas ja vem no tamanho original (o zoom continua ao trocar de foto)
  function precarrega() { [i + 1, i - 1, i + 2].forEach(k => { if (k >= 0 && k < lista.length) new Image().src = `/api/revisor/imagem/${k}?${zoom.precisaOriginal() && k === i + 1 ? 'lado=0&' : ''}v=${v}`; }); }
  function mostra() {
    const d = desc.has(i);
    zoom.foto(`/api/revisor/imagem/${i}?v=${v}`, `/api/revisor/imagem/${i}?lado=0&v=${v}`); $('#r-stage').classList.toggle('desc', d); $('#r-stamp').classList.toggle('hidden', !d);
    const rest = lista.length - desc.size;
    $('#r-info').innerHTML = `<b>Foto ${i + 1}/${lista.length}</b> · ${esc(lista[i])}<br><span class="mini" style="color:#aaa">${desc.size} marcada(s) para descarte · ${rest} mantida(s)</span>`;
    $('#r-undo').disabled = !ordemDesc.length;
    $('#r-strip').querySelectorAll('img').forEach(t => { const k = +t.dataset.k; t.classList.toggle('cur', k === i); t.classList.toggle('desc', desc.has(k)); });
    const cur = $('#r-strip').querySelector('img.cur'); if (cur) cur.scrollIntoView({ block: 'nearest', inline: 'center' });
    precarrega();
  }
  const prox = () => { if (i < lista.length - 1) { i++; mostra(); } }, ant = () => { if (i > 0) { i--; mostra(); } };
  function descartar() { if (!desc.has(i)) { desc.add(i); ordemDesc.push(i); } if (i < lista.length - 1) i++; mostra(); }
  function desfazer() { if (!ordemDesc.length) return; const k = ordemDesc.pop(); desc.delete(k); i = k; mostra(); }
  async function fechar() { document.removeEventListener('keydown', tecla); zoom.destruir(); el.remove(); await render(); }
  async function finalizar() {
    let msg = 'Revisão terminada! Nenhuma foto foi apagada.';
    if (desc.size) {
      if (!await confirmar('Confirmar Exclusão', `Você marcou ${desc.size} foto(s) para exclusão.\n\nElas serão apagadas permanentemente do computador.\nDeseja continuar?`, 'Apagar', 'Voltar')) return;
    }
    try {
      const r = await api('/api/revisor/finalizar', { body: { descartar: [...desc] } });
      if (desc.size) msg = `Limpeza concluída! ${r.apagadas} foto(s) foram apagadas.` + (r.erros ? `\n(Erro ao apagar ${r.erros} foto(s).)` : '');
      document.removeEventListener('keydown', tecla); zoom.destruir(); el.remove();
      await alerta(desc.size ? 'Sucesso' : 'Concluído', msg);
      api('/api/revisor/abrir-pasta', { body: {} }).catch(() => { });
      render();
    } catch (e) { toast(e.message, true); }
  }
  async function sair() {
    const r = await tri('Finalizar Seleção', "Deseja salvar suas escolhas e finalizar a revisão?\n\n- 'Salvar': aplica as exclusões permanentemente.\n- 'Sair sem salvar': fecha mantendo todas as fotos.\n- 'Continuar': volta à revisão.", 'Salvar', 'Sair sem salvar', 'Continuar');
    if (r === true) finalizar(); else if (r === false) fechar();
  }
  function tecla(e) {
    if (document.querySelector('.modal-bg')) return;
    if (e.key === 'ArrowRight') prox(); else if (e.key === 'ArrowLeft') ant();
    else if (['Delete', 'Backspace', 'x', 'X'].includes(e.key)) { e.preventDefault(); descartar(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); desfazer(); }
    else if (e.key === 'Enter') finalizar(); else if (e.key === 'Escape') sair();
    else if (e.key === '+' || e.key === '=') zoom.mais(); else if (e.key === '-' || e.key === '_') zoom.menos();
    else if (e.key === '0') zoom.ajustar(); else if (e.key === '1') zoom.cem();
  }
  document.addEventListener('keydown', tecla);
  $('#r-ant').onclick = ant; $('#r-prox').onclick = prox; $('#r-desc').onclick = descartar; $('#r-undo').onclick = desfazer;
  $('#r-fim').onclick = finalizar; $('#r-sair').onclick = sair;
  $('#r-zm').onclick = zoom.menos; $('#r-zp').onclick = zoom.mais; $('#r-zt').onclick = zoom.alternar;
  mostra();
}

// ---------- HISTORICO ----------
async function vHistorico() {
  const h = await api('/api/historico');
  $app.innerHTML = `<div class="wrap"><div class="topbar"><h1>📊 Histórico de Descarregamentos</h1><div class="acts"><button class="verm" id="h-limpar">🗑 Limpar histórico</button><button class="cinza" id="h-v">⬅ Voltar</button></div></div>
  ${h.map(x => { const d = (x.data || '').split('-'); const dt = d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : x.data;
    return `<div class="item"><span class="t">📅 ${esc(dt)} às ${esc(x.hora)}<br>👤 Fotógrafo: ${esc(x.fotografo)}<br>📥 Copiadas: ${x.descarregadas} | ✅ Selecionadas: ${x.selecionadas}<br><span class="mut mini">📁 ${esc(x.destino)}</span></span><button class="pq" data-p="${esc(x.destino)}">📁 Abrir Pasta</button></div>`; }).join('') || '<p class="mut">Nenhum registro de descarregamento encontrado.</p>'}</div>`;
  $app.querySelector('#h-v').onclick = () => ir('home');
  $app.querySelector('#h-limpar').onclick = async () => { if (await confirmar('Limpar Histórico', 'Deseja realmente limpar todo o histórico de dados?')) { await api('/api/historico', { method: 'DELETE' }); vHistorico(); } };
  $app.querySelectorAll('[data-p]').forEach(b => b.onclick = () => api('/api/fs/abrir', { body: { path: b.dataset.p } }).catch(() => alerta('Pasta Não Encontrada', `A pasta '${b.dataset.p}' não existe ou foi movida/deletada.`)));
}

// ---------- CONFIG DRIVE / PASTAS LOCAIS ----------
async function vDrive() {
  const cfg = S.cfg || (S.cfg = await api('/api/config'));
  $app.innerHTML = `<div class="wrap"><div class="topbar"><h1>⚙️ Configuração de Pastas</h1><div class="acts"><button data-go="google">🔑 Conta Google</button><button class="cinza" id="d-v">⬅ Voltar</button></div></div>
  <p class="mut">As pastas configuradas valem apenas para o dia de hoje (${new Date().toLocaleDateString('pt-BR')}).</p>
  <div class="grid"><div class="card"><h2>☁️ Pastas do Google Drive</h2>
   <input type="text" id="d-nome" placeholder="Nome de exibição (opcional)" style="margin-bottom:6px"><div class="row"><input type="text" id="d-link" placeholder="Link ou ID da pasta"><button class="fix" id="d-add">Adicionar</button></div>
   ${cfg.pastas.map((p, i) => `<div class="item"><span class="t">☁️ ${esc(p.nome)}<br><span class="mut mini">${esc(p.link)}</span></span><a href="https://drive.google.com/drive/folders/${encodeURIComponent(p.link.split('/folders/').pop().split('?')[0])}" target="_blank"><button class="pq cinza">Abrir</button></a><button class="verm pq" data-rd="${i}">Remover</button></div>`).join('') || '<p class="mut mini">Nenhuma pasta.</p>'}</div>
  <div class="card"><h2>💻 Pastas locais de destino</h2>
   <input type="text" id="l-nome" placeholder="Nome de exibição (opcional)" style="margin-bottom:6px"><div class="row"><input type="text" id="l-cam" placeholder="Caminho da pasta"><button class="fix cinza" id="l-proc">Procurar</button><button class="fix" id="l-add">Adicionar</button></div>
   ${cfg.pastas_local.map((p, i) => `<div class="item"><span class="t">💻 ${esc(p.nome)}<br><span class="mut mini">${esc(p.caminho)}</span></span><button class="pq cinza" data-ol="${i}">Abrir</button><button class="verm pq" data-rl="${i}">Remover</button></div>`).join('') || '<p class="mut mini">Nenhuma pasta.</p>'}</div></div>
  <button class="verde grande" id="d-salvar">💾 Salvar e Fechar</button></div>`;
  const q = s => $app.querySelector(s);
  $app.querySelectorAll('[data-go]').forEach(b => b.onclick = () => ir(b.dataset.go));
  q('#d-v').onclick = () => { S.cfg = null; ir('home'); };
  q('#d-add').onclick = async () => {
    const link = q('#d-link').value.trim(); let nome = q('#d-nome').value.trim(); if (!link) return;
    if (!nome) { try { nome = (await api('/api/drive/nome-pasta?link=' + encodeURIComponent(link))).nome || ''; } catch (e) { } }
    cfg.pastas.push({ nome: nome || 'Pasta do Google Drive', link }); vDrive();
  };
  q('#l-proc').onclick = async () => { const p = await escolherPasta('Pasta local de destino', q('#l-cam').value); if (p) q('#l-cam').value = p; };
  q('#l-add').onclick = () => { const c = q('#l-cam').value.trim(); if (!c) return; cfg.pastas_local.push({ nome: q('#l-nome').value.trim() || c.split(/[\\/]/).filter(Boolean).pop() || c, caminho: c }); vDrive(); };
  $app.querySelectorAll('[data-rd]').forEach(b => b.onclick = () => { cfg.pastas.splice(b.dataset.rd, 1); vDrive(); });
  $app.querySelectorAll('[data-rl]').forEach(b => b.onclick = () => { cfg.pastas_local.splice(b.dataset.rl, 1); vDrive(); });
  $app.querySelectorAll('[data-ol]').forEach(b => b.onclick = () => api('/api/fs/abrir', { body: { path: cfg.pastas_local[b.dataset.ol].caminho } }).catch(e => toast(e.message, true)));
  q('#d-salvar').onclick = async () => { await api('/api/config', { method: 'PUT', body: cfg }); S.cfg = null; toast('Configurações salvas!'); ir('home'); };
}

// ---------- CONTA GOOGLE ----------
async function vGoogle() {
  const g = await api('/api/google/status');
  $app.innerHTML = `<div class="wrap"><div class="topbar"><h1>🔑 Conta Google</h1><div class="acts"><button class="cinza" id="g-v">⬅ Voltar</button></div></div>
  ${g.disponivel ? '' : '<p class="bad">As bibliotecas do Google não estão instaladas (pip install -r requirements.txt).</p>'}
  <div class="grid"><div class="card"><h2>1. Credenciais OAuth</h2>
    <p>Status: <b class="${g.tem_credenciais ? 'ok' : 'warn'}">${g.tem_credenciais ? '✅ credentials.json configurado' : '⚠️ não configurado'}</b></p>
    <label>Client ID</label><input type="text" id="g-id"><label>Client Secret</label><input type="password" id="g-sec">
    <label style="font-weight:400"><input type="checkbox" id="g-show"> mostrar segredo</label>
    <button id="g-salvar" style="margin-top:8px">Salvar credenciais</button>
    <h3>Ou importe o arquivo JSON do Google Cloud</h3><input type="file" id="g-file" accept=".json">
    <p class="mut mini">Também é possível usar o arquivo .env (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET). Veja <code>google_drive_credentials_guide.md</code>.</p></div>
   <div class="card"><h2>2. Login e conexão</h2>
    <p>Token: <b class="${g.tem_token ? 'ok' : 'warn'}">${g.tem_token ? '✅ token.json gerado' : '⚠️ sem login'}</b></p>
    <p class="mut mini">O login abre uma janela do navegador <b>no computador que roda o servidor</b> para você autorizar o acesso.</p>
    <div class="row"><button class="verde" id="g-login">🔑 Fazer Login no Google</button><button id="g-test">🧪 Testar conexão</button></div>
    <button class="verm" id="g-desc" style="margin-top:8px">Desconectar conta</button>
    <p id="g-msg" class="${g.login.estado === 'erro' ? 'bad' : 'mut'}">${esc(g.login.msg)}</p><p id="g-conta" class="ok"></p></div></div></div>`;
  const q = s => $app.querySelector(s);
  q('#g-v').onclick = () => ir('home');
  q('#g-show').onchange = e => { q('#g-sec').type = e.target.checked ? 'text' : 'password'; };
  q('#g-salvar').onclick = async () => { try { await api('/api/google/credenciais', { body: { client_id: q('#g-id').value, client_secret: q('#g-sec').value } }); toast('Credenciais salvas!'); vGoogle(); } catch (e) { toast(e.message, true); } };
  q('#g-file').onchange = async e => { const f = e.target.files[0]; if (!f) return; try { await api('/api/google/importar', { body: { conteudo: await f.text() } }); toast('Arquivo importado!'); vGoogle(); } catch (er) { toast(er.message, true); } };
  q('#g-login').onclick = async () => {
    try { await api('/api/google/login', { body: {} }); q('#g-msg').textContent = 'Aguardando autorização no navegador...';
      iniciarPoll(async () => { const s = await api('/api/google/status'); q('#g-msg').textContent = s.login.msg;
        if (s.login.estado !== 'aguardando') { pararPoll(); if (s.login.estado === 'ok') { toast('Login efetuado!'); vGoogle(); } else q('#g-msg').className = 'bad'; } }, 1500);
    } catch (e) { toast(e.message, true); }
  };
  q('#g-test').onclick = async () => { q('#g-msg').textContent = '🧪 Testando conexão com a API do Google Drive...'; try { const c = await api('/api/google/testar', { body: {} }); q('#g-conta').textContent = `👤 ${c.nome} (${c.email})`; q('#g-msg').textContent = `✅ Conexão bem-sucedida! Logado como ${c.email}`; } catch (e) { q('#g-msg').className = 'bad'; q('#g-msg').textContent = '❌ ' + e.message; } };
  q('#g-desc').onclick = async () => { if (await confirmar('Confirmar Desconexão', 'Deseja realmente desconectar a conta do Google e remover o token.json?')) { await api('/api/google/desconectar', { body: {} }); toast('Conta desconectada.'); vGoogle(); } };
}

// ---------- painel de envios ao Drive (segundo plano, visivel em qualquer tela) ----------
const $up = document.createElement('div'); $up.id = 'uploads'; $up.className = 'hidden'; document.body.appendChild($up);
let upMin = false, upUlt = '';
function uploadsDesenha(lista) {
  const chave = JSON.stringify(lista) + upMin;
  if (chave === upUlt) return; upUlt = chave;
  document.body.classList.toggle('com-uploads', lista.length > 0);
  if (!lista.length) { $up.classList.add('hidden'); return; }
  $up.classList.remove('hidden');
  const ativos = lista.filter(j => j.estado === 'fila' || j.estado === 'rodando');
  const feitos = lista.reduce((a, j) => a + j.feitos, 0), total = lista.reduce((a, j) => a + j.total, 0);
  const titulo = ativos.length ? `☁️ Enviando ao Drive · ${ativos.length} em andamento` : '☁️ Envios ao Drive concluídos';
  $up.innerHTML = `<div class="uphead"><b>${titulo}</b><span><button class="pq cinza" id="up-min">${upMin ? '▢' : '–'}</button>${ativos.length ? '' : '<button class="pq cinza" id="up-x">✕</button>'}</span></div>
    ${upMin ? `<progress value="${total ? feitos / total : 0}" max="1"></progress>` : lista.slice().reverse().map(j => `<div class="upjob ${j.estado}">
      <div class="uprow"><span>${j.estado === 'concluido' ? '✅' : j.estado === 'erro' ? '⚠️' : j.estado === 'fila' ? '⏳' : '⬆'} <b>${esc(j.fotografo)}</b></span><span class="mini">${j.feitos}/${j.total}</span></div>
      <progress value="${j.progresso}" max="1"></progress>
      ${j.estado === 'rodando' && (j.atuais || []).length ? `<div class="upfiles">${j.atuais.map(n => `<div title="${esc(n)}">📄 ${esc(n)}</div>`).join('')}</div>` : ''}
      <div class="mini mut">${esc(j.estado === 'concluido' || j.estado === 'erro' ? j.msg : j.estado === 'fila' ? 'Na fila de envio...' : 'Enviando para ' + j.destino)}${j.erros ? ` · <span class="bad">${j.erros} com erro</span>` : ''}</div></div>`).join('')}`;
  $up.querySelector('#up-min').onclick = () => { upMin = !upMin; upUlt = ''; uploadsAtualiza(); };
  const x = $up.querySelector('#up-x'); if (x) x.onclick = async () => { await api('/api/uploads/limpar', { body: {} }); upUlt = ''; uploadsAtualiza(); };
}
// arrastar pelo cabecalho (mouse ou toque); a posicao fica salva no navegador
function upPosiciona(x, y) {
  const w = $up.offsetWidth, h = $up.offsetHeight;
  x = Math.max(0, Math.min(x, innerWidth - w)); y = Math.max(0, Math.min(y, innerHeight - Math.min(h, 60)));
  $up.style.left = x + 'px'; $up.style.top = y + 'px'; $up.style.right = 'auto';
  return { x, y };
}
try { const pos = JSON.parse(localStorage.getItem('uploadsPos') || 'null'); if (pos) upPosiciona(pos.x, pos.y); } catch (e) { }
let upDrag = null;
$up.addEventListener('pointerdown', e => {
  if (!e.target.closest('.uphead') || e.target.closest('button')) return;
  const r = $up.getBoundingClientRect(); upDrag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
  $up.setPointerCapture(e.pointerId); $up.classList.add('arrastando'); e.preventDefault();
});
$up.addEventListener('pointermove', e => { if (upDrag) upPosiciona(e.clientX - upDrag.dx, e.clientY - upDrag.dy); });
const upSolta = () => {
  if (!upDrag) return; upDrag = null; $up.classList.remove('arrastando');
  try { const r = $up.getBoundingClientRect(); localStorage.setItem('uploadsPos', JSON.stringify({ x: r.left, y: r.top })); } catch (e) { }
};
$up.addEventListener('pointerup', upSolta); $up.addEventListener('pointercancel', upSolta);
addEventListener('resize', () => { if ($up.style.left) { const r = $up.getBoundingClientRect(); upPosiciona(r.left, r.top); } });
let upAtivosAntes = 0;
async function uploadsAtualiza() {
  try {
    const l = await api('/api/uploads'); uploadsDesenha(l);
    const ativos = l.filter(j => j.estado === 'fila' || j.estado === 'rodando').length;
    if (ativos < upAtivosAntes) { const ult = l.filter(j => j.estado === 'concluido' || j.estado === 'erro').pop(); if (ult) toast(ult.estado === 'erro' ? `⚠️ Envio de ${ult.fotografo} terminou com erros` : `✅ Envio de ${ult.fotografo} concluído`, ult.estado === 'erro'); }
    upAtivosAntes = ativos;
  } catch (e) { }
}
setInterval(uploadsAtualiza, 1500); uploadsAtualiza();

// ---------- atualizacao automatica (programa instalado) ----------
// o programa fecha e reabre na versao nova sozinho; a tela mostra o andamento e recarrega quando ele volta
const $atu = document.createElement('div'); $atu.className = 'banner hidden'; document.body.prepend($atu);
let verVista = null, instalando = false, semConexao = false;
function bannerAtualizacao(a) {
  const mostrar = a && ['pronta', 'instalando', 'manual'].includes(a.estado);
  $atu.classList.toggle('hidden', !mostrar); if (!mostrar) return;
  $atu.style.background = a.estado === 'instalando' ? 'var(--lar)' : '';
  $atu.innerHTML = (a.estado === 'instalando' ? '🔄 ' : a.estado === 'pronta' ? '⬇️ ' : '') + esc(a.msg) +
    (a.estado === 'manual' && a.url ? ' <button id="atu-baixar">⬇ Baixar</button>' : '');
  const b = $atu.querySelector('#atu-baixar'); if (b) b.onclick = () => window.open(a.url, '_blank');
}
async function vigiaAtualizacao() {
  if (S.encerrado) return;
  try {
    const st = await api('/api/state');
    if (verVista && st.versao !== verVista) {         // voltou na versao nova: recarrega a tela
      try { if (S.entrou) sessionStorage.setItem('voltarDescarregar', '1'); } catch (e) { }
      return location.reload();
    }
    verVista = st.versao; instalando = st.atualizacao && st.atualizacao.estado === 'instalando';
    bannerAtualizacao(st.atualizacao);
    if (semConexao) { semConexao = false; render(); }  // o programa voltou (mesma versao, se a instalacao falhou)
  } catch (e) {
    semConexao = true;
    if (instalando) bannerAtualizacao({ estado: 'instalando', msg: 'Atualizando o programa… a tela volta sozinha em instantes.' });
  }
}
setInterval(vigiaAtualizacao, 4000); vigiaAtualizacao();
try { if (sessionStorage.getItem('voltarDescarregar')) { sessionStorage.removeItem('voltarDescarregar'); S.entrou = true; } } catch (e) { }

render();
