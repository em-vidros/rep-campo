/* REP Campo - PWA offline-first. Versao 1.0.0 */
'use strict';
const VERSAO = '1.0.0';

/* ---------------------------------------------------------------- IndexedDB */
const BD_NOME = 'rep-campo', BD_VER = 1;
let bd = null;

function abrirBD() {
  return new Promise((ok, falha) => {
    const req = indexedDB.open(BD_NOME, BD_VER);
    req.onupgradeneeded = ev => {
      const d = ev.target.result;
      if (!d.objectStoreNames.contains('fila')) d.createObjectStore('fila', { keyPath: 'uuid' });
      if (!d.objectStoreNames.contains('cache')) d.createObjectStore('cache', { keyPath: 'chave' });
      if (!d.objectStoreNames.contains('enviadas')) d.createObjectStore('enviadas', { keyPath: 'uuid' });
    };
    req.onsuccess = () => { bd = req.result; ok(bd); };
    req.onerror = () => falha(req.error);
  });
}
function tx(store, modo, fn) {
  return new Promise((ok, falha) => {
    const t = bd.transaction(store, modo), s = t.objectStore(store), r = fn(s);
    t.oncomplete = () => ok(r && r.result !== undefined ? r.result : r);
    t.onerror = () => falha(t.error);
  });
}
const filaPor    = ()   => tx('fila', 'readonly', s => s.getAll());
const filaSalvar = f    => tx('fila', 'readwrite', s => s.put(f));
const filaTirar  = id   => tx('fila', 'readwrite', s => s.delete(id));
const cacheLer   = c    => tx('cache', 'readonly', s => s.get(c));
const cacheGravar= (c,v)=> tx('cache', 'readwrite', s => s.put({ chave: c, valor: v }));
const enviadasPor= ()   => tx('enviadas', 'readonly', s => s.getAll());
const enviadaSalvar = f => tx('enviadas', 'readwrite', s => s.put(f));

/* ------------------------------------------------------------------ estado */
// Tres fichas por envio. Cada ficha carrega a foto principal mais ate tres
// evidencias em base64, e a Vercel recusa requisicao acima de 4,5 MB.
const LOTE_SYNC = 3;
let CFG = { clientes: [], municipios: [], relato_min: 200 };
let tipoAtual = null, fotoDataUrl = null, geo = { lat: null, lon: null, precisao: null };

/* ------------------------------------------------------------------- utils */
const $ = id => document.getElementById(id);
function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
function aviso(msg, erro) {
  const el = $('aviso');
  el.textContent = msg;
  el.className = 'aviso' + (erro ? ' erro' : '');
  setTimeout(() => el.classList.add('oculto'), 3600);
}
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* -------------------------------------------------------------- campos/tipo */
const CAMPOS = {
  comercial: [
    { id: 'oportunidade', rot: 'Houve oportunidade?', tipo: 'select', ops: ['sim', 'nao'] },
    { id: 'produto', rot: 'Produto / linha', tipo: 'text' },
    { id: 'valor_estimado', rot: 'Valor estimado (R$)', tipo: 'number' },
    { id: 'prazo', rot: 'Prazo esperado', tipo: 'text', ph: 'ex: proximos 15 dias' },
  ],
  cordialidade: [
    { id: 'termometro', rot: 'Termometro do relacionamento', tipo: 'select', ops: ['1 - frio', '2', '3 - neutro', '4', '5 - quente'] },
    { id: 'assunto', rot: 'Assunto tratado', tipo: 'text' },
    { id: 'risco', rot: 'Percebi risco de perder o cliente?', tipo: 'select', ops: ['nao', 'sim'] },
    { id: 'risco_qual', rot: 'Qual risco', tipo: 'text' },
  ],
  tecnica: [
    { id: 'pedido_nf', rot: 'Numero do pedido ou NF', tipo: 'text' },
    { id: 'problema_tipo', rot: 'Tipo de ocorrencia *', tipo: 'problemas' },
    { id: 'problema_outros', rot: 'Qual? (se marcou Outros)', tipo: 'text' },
    { id: 'resolvido_local', rot: 'Resolvido no local?', tipo: 'select', ops: ['nao', 'sim'] },
    { id: 'prazo_prometido', rot: 'Prazo prometido ao cliente', tipo: 'date' },
    { id: 'responsavel_interno', rot: 'Quem foi acionado internamente', tipo: 'text' },
  ],
  prospeccao: [
    { id: 'razao_social', rot: 'Razao social', tipo: 'text' },
    { id: 'cnpj', rot: 'CNPJ', tipo: 'text', ph: 'so numeros' },
    { id: 'porte', rot: 'Porte', tipo: 'select', ops: ['pequeno', 'medio', 'grande'] },
    { id: 'compra_de_quem', rot: 'Compra hoje de quem', tipo: 'text' },
    { id: 'potencial_mes', rot: 'Potencial estimado por mes (R$)', tipo: 'number' },
    { id: 'interesse', rot: 'Interesse', tipo: 'select', ops: ['1 - nenhum', '2', '3', '4', '5 - alto'] },
  ],
  preco: [
    { id: 'concorrente', rot: 'Concorrente pesquisado', tipo: 'text' },
    { id: 'itens', rot: 'Itens e precos', tipo: 'itens' },
    { id: 'condicao_pagamento', rot: 'Condicao de pagamento praticada', tipo: 'text' },
    { id: 'prazo_entrega', rot: 'Prazo de entrega praticado', tipo: 'text' },
  ],
  voz: [
    { id: 'nota', rot: 'De 0 a 10, o quanto recomendaria a EM Vidros?', tipo: 'select',
      ops: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] },
    { id: 'motivo', rot: 'Motivo da nota (palavras do cliente)', tipo: 'textarea' },
    { id: 'tema', rot: 'Tema principal', tipo: 'select',
      ops: ['preco', 'prazo', 'qualidade', 'atendimento', 'mix de produtos', 'outro'] },
    { id: 'autoriza_contato', rot: 'Autoriza contato da gerencia?', tipo: 'select', ops: ['sim', 'nao'] },
  ],
  evento: [
    { id: 'nome_evento', rot: 'Nome do evento', tipo: 'text' },
    { id: 'local', rot: 'Local', tipo: 'text' },
    { id: 'contatos_gerados', rot: 'Quantos contatos gerados', tipo: 'number' },
    { id: 'principais_contatos', rot: '3 principais contatos', tipo: 'textarea' },
    { id: 'leitura', rot: 'Leitura do evento', tipo: 'textarea' },
  ],
};
const FOTO_OBRIGATORIA = ['tecnica', 'prospeccao', 'preco', 'evento'];

function montarCampos(tipo) {
  const box = $('campos-tipo');
  box.innerHTML = '';
  (CAMPOS[tipo] || []).forEach(c => {
    const wrap = document.createElement('label');
    wrap.textContent = c.rot;
    let el;
    if (c.tipo === 'select') {
      el = document.createElement('select');
      el.innerHTML = '<option value=""></option>' +
        c.ops.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('');
    } else if (c.tipo === 'textarea') {
      el = document.createElement('textarea'); el.rows = 3;
    } else if (c.tipo === 'problemas') {
      el = document.createElement('select');
      el.innerHTML = '<option value=""></option>' +
        (CFG.problemas || []).map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
    } else if (c.tipo === 'itens') {
      el = document.createElement('div');
      el.className = 'itens-preco';
      // cesta fixa: os mesmos itens todo mes, senao nao da para comparar
      let grupoAtual = '';
      const linhas = (CFG.cesta_preco || []).map(x => {
        const cab = x.grupo !== grupoAtual
          ? `<div class="grupo-cesta">${esc(x.grupo)}</div>` : '';
        grupoAtual = x.grupo;
        return cab + `<div class="linha-item">
          <span class="nome-item">${esc(x.item)}</span>
          <input placeholder="R$" inputmode="decimal" data-i-preco
                 data-i-nome-fixo="${esc(x.item)}">
        </div>`;
      }).join('');
      el.innerHTML = linhas +
        '<div class="grupo-cesta">Outros itens</div>' +
        '<div class="dupla"><input placeholder="item" data-i-nome><input placeholder="R$" inputmode="decimal" data-i-preco></div>'.repeat(2) +
        '<button type="button" class="mini" id="btn-mais-item">+ item</button>';
    } else {
      el = document.createElement('input');
      el.type = c.tipo;
      if (c.ph) el.placeholder = c.ph;
      if (c.tipo === 'number') el.inputMode = 'decimal';
    }
    el.id = 'x-' + c.id;
    wrap.appendChild(el);
    box.appendChild(wrap);
  });
  const btn = $('btn-mais-item');
  if (btn) btn.onclick = () => {
    const d = document.createElement('div');
    d.className = 'dupla';
    d.innerHTML = '<input placeholder="item" data-i-nome><input placeholder="R$" inputmode="decimal" data-i-preco>';
    btn.parentNode.insertBefore(d, btn);
  };
  const obrig = FOTO_OBRIGATORIA.includes(tipo);
  const dicaFoto = 'A foto é a prova de que a visita aconteceu e do que foi visto. '
    + 'Em reclamação, fotografe o defeito; em pesquisa de preço, o orçamento ou a tabela.';
  $('rotulo-foto').innerHTML = (obrig
    ? 'Foto <b class="obrig">obrigatoria neste tipo</b>'
    : 'Foto <span class="dica">(opcional)</span>')
    + ' <span class="dica-ajuda" data-dica="' + dicaFoto + '">?</span>';
  $('wrap-encaminhado').classList.toggle('oculto', !['comercial', 'prospeccao', 'tecnica'].includes(tipo));
}

/* Pesquisa de experiencia - vai em TODA visita, com pergunta pertinente ao tipo.
   Um toque obrigatorio (a nota); o resto e opcional, para nao passar de 2 min. */
function montarExperiencia(tipo) {
  const box = $('bloco-experiencia');
  if (tipo === 'voz') return montarPesquisaCompleta(box);
  const par = (CFG.pergunta_experiencia || {})[tipo] ||
    ['Relacionamento geral', 'Como esta sendo a experiencia com a gente?'];
  const [etapaPadrao, pergunta] = par;
  const prospect = tipo === 'prospeccao';

  box.innerHTML = `
    <fieldset class="bloco-exp">
      <legend>Experiencia do cliente <b class="obrig">${prospect ? 'opcional' : 'nota obrigatoria'}</b>
        <span class="dica-ajuda" data-dica="Uma nota, um toque. A régua é sempre 0 a 10, mas o que ela mede muda conforme a etapa: recomendação da marca, satisfação com um processo, ou o esforço que o cliente teve para resolver um problema.">?</span></legend>
      <small class="dica" id="txt-pergunta">${esc(pergunta)}</small>
      <div class="notas" id="notas-exp">
        ${Array.from({ length: 11 }, (_, n) =>
          `<button type="button" class="nota" data-nota="${n}">${n}</button>`).join('')}
      </div>
      <div class="reguas"><span id="regua-min"></span><span id="regua-max"></span></div>
      <div id="aviso-nps" class="aviso-curto oculto"></div>
      <label>O que ele avaliou
        <span class="dica-ajuda" data-dica="A etapa da jornada de compra a que a nota se refere. Muda o significado da régua: em Relacionamento geral é recomendação da marca; em Pós-venda é o esforço que o cliente teve para resolver.">?</span>
        <select id="f-exp-etapa">
          ${(CFG.etapas_jornada || []).map(e =>
            `<option value="${esc(e)}"${e === etapaPadrao ? ' selected' : ''}>${esc(e)}</option>`).join('')}
        </select>
        <small class="dica" id="txt-metrica"></small>
      </label>
      <label>Nas palavras dele (opcional)
        <textarea id="f-exp-comentario" rows="2" placeholder="o que ele falou, do jeito que falou"></textarea>
      </label>
    </fieldset>`;

  box.querySelectorAll('.nota').forEach(b => b.onclick = () => {
    box.querySelectorAll('.nota').forEach(x => x.classList.remove('escolhida'));
    b.classList.add('escolhida');
    box.dataset.nota = b.dataset.nota;
  });
  delete box.dataset.nota;

  $('f-exp-etapa').onchange = ajustarMetrica;
  ajustarMetrica();
}

/* Voz do Cliente E a pesquisa: avalia os processos da empresa, nao so uma
   etapa. NPS obrigatorio; cada processo e opcional (pode nao se aplicar). */
function montarPesquisaCompleta(box) {
  const linhas = (CFG.processos_csat || []).map((p, i) => {
    const proc = typeof p === 'string' ? { item: p } : p;
    const unidades = proc.unidades
      ? `<label class="rotulo-unidade">De qual unidade?
           <select class="unidade-proc" data-unidade="${esc(proc.item)}">
             <option value="">selecione a expedição</option>
             ${proc.unidades.map(u => `<option value="${esc(u)}">${esc(u)}</option>`).join('')}
           </select></label>` : '';
    return `<div class="proc">
      <div class="proc-nome">${esc(proc.item)}
        ${proc.condicional ? `<small class="dica">${esc(proc.condicional)}</small>` : ''}</div>
      <div class="proc-notas" data-proc="${esc(proc.item)}">
        ${Array.from({ length: 11 }, (_, n) =>
          `<button type="button" class="nota-min" data-n="${n}">${n}</button>`).join('')}
        <button type="button" class="nota-min pular" data-n="">n/a</button>
      </div>
      ${unidades}
    </div>`;
  }).join('');

  box.innerHTML = `
    <fieldset class="bloco-exp">
      <legend>Pesquisa de satisfação <b class="obrig">NPS obrigatório</b>
        <span class="dica-ajuda" data-dica="A pesquisa completa: primeiro a nota de recomendação da marca, depois a satisfação com cada processo da empresa. Toque em n/a no que não se aplica àquele cliente.">?</span></legend>

      <small class="dica"><b>De 0 a 10, o quanto recomendaria a EM Vidros?</b></small>
      <div class="notas" id="notas-exp">
        ${Array.from({ length: 11 }, (_, n) =>
          `<button type="button" class="nota" data-nota="${n}">${n}</button>`).join('')}
      </div>
      <div class="reguas"><span>0 = não recomendaria</span><span>10 = com certeza</span></div>
      <div id="aviso-nps" class="aviso-curto oculto"></div>
      <label>Motivo da nota (palavras do cliente)
        <textarea id="f-exp-comentario" rows="2" placeholder="o que ele falou, do jeito que falou"></textarea>
      </label>

      <div class="titulo-proc">Satisfação com cada processo
        <span class="dica-ajuda" data-dica="Cada linha é um processo da empresa. O cliente dá a nota que sentir; o que não se aplica a ele, toque em n/a. É o que mostra onde a empresa está boa e onde dói.">?</span>
        <small class="dica">0 = muito insatisfeito · 10 = muito satisfeito · toque em
          <b>n/a</b> no que não se aplica</small></div>
      ${linhas}

      <label>Observação geral da pesquisa (opcional)
        <textarea id="f-obs-pesquisa" rows="2" placeholder="algo que ele falou e não cabe nas notas"></textarea>
      </label>
      <input type="hidden" id="f-exp-etapa" value="Relacionamento geral">
    </fieldset>`;

  box.querySelectorAll('#notas-exp .nota').forEach(b => b.onclick = () => {
    box.querySelectorAll('#notas-exp .nota').forEach(x => x.classList.remove('escolhida'));
    b.classList.add('escolhida');
    box.dataset.nota = b.dataset.nota;
    avisarFadigaNps();
  });
  box.querySelectorAll('.proc-notas').forEach(linha =>
    linha.querySelectorAll('.nota-min').forEach(b => b.onclick = () => {
      linha.querySelectorAll('.nota-min').forEach(x => x.classList.remove('escolhida'));
      b.classList.add('escolhida');
      linha.dataset.nota = b.dataset.n;
      // marcou n/a: a unidade nao se aplica mais
      const sel = linha.parentNode.querySelector('.unidade-proc');
      if (sel && !b.dataset.n) sel.value = '';
    }));
  delete box.dataset.nota;
}

/* Junta as respostas: nas visitas comuns e uma; na Voz do Cliente sao varias. */
function lerExperiencia() {
  const box = $('bloco-experiencia');
  const geral = box.dataset.nota;
  const comentario = ($('f-exp-comentario') || {}).value || null;
  const respostas = [];
  if (geral !== undefined && geral !== '') {
    respostas.push({
      etapa: ($('f-exp-etapa') || {}).value || 'Relacionamento geral',
      nota: Number(geral), comentario,
    });
  }
  box.querySelectorAll('.proc-notas').forEach(linha => {
    if (!linha.dataset.nota) return;              // n/a ou nao respondido
    const sel = linha.parentNode.querySelector('.unidade-proc');
    respostas.push({
      etapa: linha.dataset.proc, nota: Number(linha.dataset.nota),
      unidade: sel ? (sel.value || null) : null,
    });
  });
  const obs = ($('f-obs-pesquisa') || {}).value;
  if (obs && respostas.length) respostas[0].comentario =
    [respostas[0].comentario, obs].filter(Boolean).join(' | ');
  return respostas;
}

/* A regua e sempre 0-10, mas o que ela significa muda com a etapa. */
const TEXTO_METRICA = {
  nps:  { nome: 'NPS', min: '0 = nao recomendaria', max: '10 = recomendaria com certeza',
          dica: 'NPS - mede lealdade a marca. Nao repita no mesmo cliente toda visita.' },
  csat: { nome: 'CSAT', min: '0 = muito insatisfeito', max: '10 = muito satisfeito',
          dica: 'CSAT - satisfacao com esta etapa especifica.' },
  ces:  { nome: 'CES', min: '0 = muito dificil', max: '10 = muito facil',
          dica: 'CES - esforco do cliente. Em pos-venda prevê recompra melhor que "recomendaria".' },
};

function ajustarMetrica() {
  const etapa = ($('f-exp-etapa') || {}).value;
  const metrica = (CFG.metrica_por_etapa || {})[etapa] || 'csat';
  const t = TEXTO_METRICA[metrica];
  $('regua-min').textContent = t.min;
  $('regua-max').textContent = t.max;
  $('txt-metrica').textContent = t.dica;

  // NPS cansa: avisa se este cliente ja respondeu ha pouco tempo
  avisarFadigaNps(metrica);
}

function avisarFadigaNps(metrica) {
  const alerta = $('aviso-nps');
  if (!alerta) return;
  alerta.classList.add('oculto');
  if (metrica === undefined) metrica = 'nps';
  if (metrica !== 'nps') return;
  const c = CFG.clientes.find(x => x.nome === ($('f-cliente').value || '').trim());
  const quando = c && (CFG.ultimo_nps || {})[c.codigo];
  if (!quando) return;
  const dias = Math.floor((Date.now() - new Date(quando)) / 86400000);
  const minimo = CFG.dias_minimos_nps || 90;
  if (dias < minimo) {
    alerta.textContent = `Este cliente já respondeu "recomendaria" há ${dias} dia(s). ` +
      `O ideal é esperar ${minimo}. Considere avaliar outra etapa da jornada.`;
    alerta.classList.remove('oculto');
  }
}

/* Evidencias extras: proposta, print de conversa, foto do material do
   concorrente. Varias por ficha, cada uma com o que e. */
let anexos = [];

function montarEvidencias(tipo) {
  const box = $('bloco-evidencias');
  const foco = tipo === 'preco'
    ? 'Proposta do concorrente, conversa do cliente com ele, foto do material'
    : 'Fotos e documentos que comprovem o que foi tratado';
  box.innerHTML = `
    <fieldset class="bloco-evid">
      <legend>Evidências <b class="obrig">opcional</b>
        <span class="dica-ajuda" data-dica="Fotos e documentos que comprovam o que foi tratado: proposta do concorrente, print de conversa, foto da peça com defeito ou do material. Marque o que é cada uma.">?</span></legend>
      <small class="dica">${esc(foco)}. Até ${CFG.max_anexos || 3}.</small>
      <input type="file" id="f-anexo" accept="image/*" multiple>
      <div id="lista-anexos" class="lista-anexos"></div>
    </fieldset>`;
  anexos = [];
  $('f-anexo').addEventListener('change', ev => {
    [...ev.target.files].forEach(arq => comprimir(arq, dataUrl => {
      if (anexos.length >= (CFG.max_anexos || 3)) return;
      anexos.push({ foto: dataUrl, tipo: (CFG.tipos_evidencia || [])[0], descricao: '' });
      desenharAnexos();
    }));
    ev.target.value = '';
  });
}

function desenharAnexos() {
  const lista = $('lista-anexos');
  lista.innerHTML = anexos.map((a, i) => `
    <div class="anexo">
      <img src="${a.foto}" alt="evidência ${i + 1}">
      <div class="anexo-campos">
        <select data-tipo="${i}">
          ${(CFG.tipos_evidencia || []).map(t =>
            `<option value="${esc(t)}"${t === a.tipo ? ' selected' : ''}>${esc(t)}</option>`).join('')}
        </select>
        <input placeholder="observação (opcional)" data-desc="${i}" value="${esc(a.descricao)}">
      </div>
      <button type="button" class="mini" data-remover="${i}">remover</button>
    </div>`).join('');
  lista.querySelectorAll('[data-tipo]').forEach(el =>
    el.onchange = () => { anexos[el.dataset.tipo].tipo = el.value; });
  lista.querySelectorAll('[data-desc]').forEach(el =>
    el.oninput = () => { anexos[el.dataset.desc].descricao = el.value; });
  lista.querySelectorAll('[data-remover]').forEach(b =>
    b.onclick = () => { anexos.splice(Number(b.dataset.remover), 1); desenharAnexos(); });
}

/* compressao no aparelho - o servidor nao processa imagem */
function comprimir(arq, pronto) {
  const leitor = new FileReader();
  leitor.onload = e => {
    const img = new Image();
    img.onload = () => {
      const max = 1280;
      let { width: w, height: h } = img;
      if (w > max || h > max) { const r = Math.min(max / w, max / h); w = Math.round(w * r); h = Math.round(h * r); }
      const cv = document.createElement('canvas');
      cv.width = w; cv.height = h;
      cv.getContext('2d').drawImage(img, 0, 0, w, h);
      pronto(cv.toDataURL('image/jpeg', 0.7));
    };
    img.src = e.target.result;
  };
  leitor.readAsDataURL(arq);
}

function lerCampos(tipo) {
  const extra = {};
  (CAMPOS[tipo] || []).forEach(c => {
    const el = $('x-' + c.id);
    if (!el) return;
    if (c.tipo === 'itens') {
      const fixos = [...el.querySelectorAll('[data-i-nome-fixo]')].map(i => ({
        item: i.dataset.iNomeFixo, preco: i.value.trim(), cesta: true,
      })).filter(x => x.preco);
      const livres = [...el.querySelectorAll('.dupla')].map(d => ({
        item: d.querySelector('[data-i-nome]').value.trim(),
        preco: d.querySelector('[data-i-preco]').value.trim(),
      })).filter(x => x.item && x.preco);
      const linhas = fixos.concat(livres);
      if (linhas.length) extra[c.id] = linhas;
    } else if (el.value && el.value.trim()) {
      extra[c.id] = el.value.trim();
    }
  });
  return extra;
}

/* ------------------------------------------------------------------ geoloc */
function pegarGeo() {
  const box = $('box-geo'), txt = $('txt-geo');
  if (!navigator.geolocation) {
    box.className = 'geo falhou'; txt.textContent = 'localizacao: nao suportada';
    return;
  }
  txt.textContent = 'localizacao: buscando...';
  box.className = 'geo';
  navigator.geolocation.getCurrentPosition(
    p => {
      geo = { lat: p.coords.latitude, lon: p.coords.longitude, precisao: p.coords.accuracy };
      box.className = 'geo ok';
      txt.textContent = 'localizacao capturada (~' + Math.round(p.coords.accuracy) + ' m)';
    },
    err => {
      geo = { lat: null, lon: null, precisao: null };
      box.className = 'geo falhou';
      txt.textContent = 'sem localizacao (' + (err.code === 1 ? 'permissao negada' : 'sinal fraco') + ') - da pra salvar assim mesmo';
    },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
  );
}

/* -------------------------------------------------------------------- foto */
$('f-foto').addEventListener('change', ev => {
  const arq = ev.target.files && ev.target.files[0];
  if (!arq) return;
  comprimir(arq, dataUrl => {
    fotoDataUrl = dataUrl;
    $('img-previa').src = dataUrl;
    $('previa-foto').classList.remove('oculto');
  });
});

/* ------------------------------------------------------------------- salvar */
$('form-ficha').addEventListener('submit', async ev => {
  ev.preventDefault();
  const erros = [];
  const cliente = $('f-cliente').value.trim();
  const municipio = $('f-municipio').value.trim();
  const objetivo = $('f-objetivo').value.trim();
  const relato = $('f-relato').value.trim();
  const passo = $('f-passo').value.trim();

  if (!cliente) erros.push('Informe o cliente.');
  if (!municipio) erros.push('Informe o municipio.');
  if (!objetivo) erros.push('Informe o objetivo da visita.');
  if (!passo) erros.push('O proximo passo e obrigatorio - sem ele a visita nao conta.');
  if (FOTO_OBRIGATORIA.includes(tipoAtual) && !fotoDataUrl)
    erros.push('Este tipo de visita exige foto.');
  if (tipoAtual === 'tecnica') {
    const tp = (document.getElementById('x-problema_tipo') || {}).value;
    const outro = (document.getElementById('x-problema_outros') || {}).value || '';
    if (!tp) erros.push('Escolha o tipo de ocorrência.');
    if (tp === 'Outros' && !outro.trim())
      erros.push('Descreva a ocorrência no campo "Qual?".');
  }

  const caixa = $('erros-form');
  if (erros.length) {
    caixa.innerHTML = erros.map(e => '- ' + esc(e)).join('<br>');
    caixa.classList.remove('oculto');
    caixa.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }
  caixa.classList.add('oculto');

  const boxExp = $('bloco-experiencia');
  const notaExp = boxExp.dataset.nota;
  if (tipoAtual !== 'prospeccao' && notaExp === undefined)
    erros.push('Dê a nota da experiência do cliente (0 a 10).');

  boxExp.querySelectorAll('.unidade-proc').forEach(sel => {
    const linha = sel.parentNode.querySelector('.proc-notas');
    if (linha && linha.dataset.nota && !sel.value)
      erros.push('Informe de qual expedição é a nota (Imperatriz, Santa Inês ou Ananindeua).');
  });

  const achado = CFG.clientes.find(c => c.nome === cliente);
  const ficha = {
    uuid: uuid(), tipo: tipoAtual,
    cliente_codigo: achado ? achado.codigo : null,
    cliente_nome: cliente,
    prospect: $('f-prospect').checked || !achado ? 1 : 0,
    municipio, objetivo, relato,
    proximo_passo: passo,
    prox_responsavel: $('f-passo-resp').value.trim(),
    prox_data: $('f-passo-data').value,
    encaminhado_para: $('f-encaminhado').value.trim(),
    lat: geo.lat, lon: geo.lon, precisao: geo.precisao,
    criado_em_disp: new Date().toISOString(),
    foto: fotoDataUrl, extra: lerCampos(tipoAtual),
    problema_tipo: (document.getElementById('x-problema_tipo') || {}).value || null,
    experiencia: lerExperiencia(),
    anexos: anexos,
    app_versao: VERSAO,
  };

  await filaSalvar(ficha);
  localStorage.removeItem('rascunho');
  limparForm();
  aviso('Ficha salva no celular.');
  atualizarStatus();
  sincronizar();
});

function limparForm() {
  $('form-ficha').reset();
  fotoDataUrl = null;
  anexos = [];
  $('previa-foto').classList.add('oculto');
  $('campos-tipo').innerHTML = '';
  $('form-ficha').classList.add('oculto');
  $('passo-tipo').classList.remove('oculto');
  $('aviso-rascunho').classList.add('oculto');
  tipoAtual = null;
}

/* ------------------------------------------------------------------- rascunho */
function salvarRascunho() {
  if (!tipoAtual) return;
  localStorage.setItem('rascunho', JSON.stringify({
    tipo: tipoAtual,
    cliente: $('f-cliente').value, municipio: $('f-municipio').value,
    objetivo: $('f-objetivo').value, relato: $('f-relato').value,
    passo: $('f-passo').value, extra: lerCampos(tipoAtual),
  }));
}
document.addEventListener('input', ev => {
  if (ev.target.closest('#form-ficha')) salvarRascunho();
});

/* ----------------------------------------------------------------- sync */
let sincronizando = false;
async function sincronizar() {
  if (sincronizando || !navigator.onLine) return;
  const fila = await filaPor();
  if (!fila.length) { atualizarStatus(); return; }
  sincronizando = true;
  try {
    const resp = await fetch('/api/fichas', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fichas: fila.slice(0, LOTE_SYNC) }),
    });
    if (resp.status === 401) { aviso('Sessao expirou. Entre de novo.', true); return; }
    if (!resp.ok) throw new Error('http ' + resp.status);
    const dados = await resp.json();
    for (const id of dados.aceitas || []) {
      const f = fila.find(x => x.uuid === id);
      if (f) { delete f.foto; f.enviado_em = new Date().toISOString(); await enviadaSalvar(f); }
      await filaTirar(id);
    }
    if ((dados.ocorrencias || []).length) {
      const nums = dados.ocorrencias.map(o => o.numero).join(', ');
      aviso('Ocorrencia aberta: ' + nums);
    } else if ((dados.aceitas || []).length) {
      aviso(dados.aceitas.length + ' ficha(s) enviada(s).');
    }
    for (const r of dados.rejeitadas || []) {
      // Ficha que o servidor recusa nunca vai entrar. Sem tirar da fila, ela fica
      // na frente para sempre e segura tudo que vier depois.
      const f = fila.find(x => x.uuid === r.uuid);
      await filaTirar(r.uuid);
      if (f) { delete f.foto; delete f.anexos; f.recusada = r.motivo || 'recusada'; await enviadaSalvar(f); }
    }
    if ((dados.rejeitadas || []).length)
      aviso(dados.rejeitadas.length + ' ficha(s) recusada(s). Veja em "Minhas fichas".', true);
  } catch (e) {
    // Offline nao e erro: a fila continua guardada e tenta de novo. Erro do
    // servidor tem que aparecer, senao o numero da fila fica parado sem
    // explicacao nenhuma na tela.
    if (navigator.onLine) aviso('Nao consegui enviar agora. Tento de novo em 1 minuto.', true);
  } finally {
    sincronizando = false;
    atualizarStatus();
    if (telaAtiva() === 'fichas') renderFichas();
  }
}

async function atualizarStatus() {
  const fila = await filaPor();
  const pc = $('pt-conexao'), pf = $('pt-fila'), bs = $('btn-sync');
  if (navigator.onLine) { pc.textContent = 'online'; pc.className = 'pastilha online'; }
  else { pc.textContent = 'sem internet'; pc.className = 'pastilha offline'; }
  if (fila.length) {
    pf.textContent = fila.length + ' na fila';
    pf.className = 'pastilha fila';
    pf.classList.remove('oculto');
    bs.classList.toggle('oculto', !navigator.onLine);
  } else { pf.classList.add('oculto'); bs.classList.add('oculto'); }
}
window.addEventListener('online', () => { atualizarStatus(); sincronizar(); });
window.addEventListener('offline', atualizarStatus);
$('btn-sync').onclick = sincronizar;

/* ---------------------------------------------------------------- telas */
const telaAtiva = () => document.querySelector('.aba.ativa').dataset.tela;
document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'fichas') renderFichas();
  if (b.dataset.tela === 'resumo') renderResumo();
});
document.querySelectorAll('.cartao-tipo').forEach(b => b.onclick = () => {
  tipoAtual = b.dataset.tipo;
  $('rotulo-tipo').textContent = b.querySelector('b').textContent;
  montarCampos(tipoAtual);
  montarExperiencia(tipoAtual);
  montarEvidencias(tipoAtual);
  $('passo-tipo').classList.add('oculto');
  $('form-ficha').classList.remove('oculto');
  pegarGeo();
  window.scrollTo(0, 0);
});
$('btn-voltar').onclick = () => { limparForm(); localStorage.removeItem('rascunho'); };
$('btn-geo').onclick = pegarGeo;

$('f-relato').addEventListener('input', ev => {
  const n = ev.target.value.trim().length, el = $('contador-relato');
  el.textContent = n + ' de ' + CFG.relato_min + ' caracteres recomendados';
  el.className = 'dica ' + (n >= CFG.relato_min ? 'bom' : (n > 0 ? 'ruim' : ''));
});
$('f-cliente').addEventListener('input', ev => {
  const c = CFG.clientes.find(x => x.nome === ev.target.value.trim());
  const cartao = $('cartao-cliente');
  if (c) {
    $('dica-cliente').textContent = '';
    const brl = v => (v || 0).toLocaleString('pt-BR',
      { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
    cartao.innerHTML = `
      <div class="cc-linha"><span>Codigo</span><b>${esc(c.codigo)}</b></div>
      <div class="cc-linha"><span>Cidade</span><b>${esc(c.cidade || '-')}</b></div>
      <div class="cc-linha"><span>Rota</span><b>${esc(c.rota || '-')}</b></div>
      <div class="cc-linha"><span>Vendedor</span><b>${esc(c.vendedor || '-')}</b></div>
      <div class="cc-linha"><span>Curva</span><b>${c.curva ? 'classe ' + esc(c.curva) : 'sem classificacao'}</b></div>
      <div class="cc-linha"><span>Comprou 12m</span><b>${brl(c.vol_12m)}</b></div>`;
    cartao.classList.remove('oculto');
    if (c.cidade && !$('f-municipio').value) $('f-municipio').value = c.cidade;
    if (c.vendedor && !$('f-encaminhado').value) {
      const primeiro = c.vendedor.trim().split(/\s+/)[0].toLowerCase();
      const dl = $('lista-responsaveis');
      const casa = dl && [...dl.options].find(o =>
        o.value.toLowerCase().startsWith(primeiro));
      // sugere quem cuida do cliente na carteira; o REP pode trocar digitando
      $('f-encaminhado').value = casa ? casa.value : c.vendedor.split(/\s+/)[0];
    }
    if (typeof ajustarMetrica === 'function' && $('f-exp-etapa')) ajustarMetrica();
  } else {
    cartao.classList.add('oculto');
    $('dica-cliente').textContent = ev.target.value.trim()
      ? 'nao encontrado na carteira: sera registrado como cliente novo' : '';
  }
});

/* ------------------------------------------------------------- renderizacao */
async function renderFichas() {
  const fila = await filaPor(), enviadas = await enviadasPor();
  const box = $('lista-fichas');
  const todas = [
    ...fila.map(f => ({ ...f, _pendente: true })),
    ...enviadas.sort((a, b) => (b.enviado_em || '').localeCompare(a.enviado_em || '')),
  ];
  if (!todas.length) { box.innerHTML = '<div class="vazio">Nenhuma ficha ainda.</div>'; return; }
  box.innerHTML = todas.slice(0, 80).map(f => {
    const selo = f.recusada ? `<span class="selo fraco">recusada: ${esc(f.recusada)}</span>`
      : f._pendente ? '<span class="selo pendente">na fila</span>'
      : '<span class="selo forte">enviada</span>';
    const d = new Date(f.criado_em_disp || Date.now());
    return `<div class="item"><div class="item-topo"><b>${esc(f.cliente_nome)}</b>${selo}</div>
      <div class="meta">${esc(f.tipo)} - ${esc(f.municipio || '')} - ${d.toLocaleDateString('pt-BR')} ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</div>
      <div class="meta">proximo passo: ${esc(f.proximo_passo || '-')}</div></div>`;
  }).join('');
}

async function renderResumo() {
  const box = $('cartoes-resumo'), det = $('detalhe-resumo');
  try {
    const r = await fetch('/api/resumo');
    if (!r.ok) throw new Error();
    const d = await r.json();
    box.innerHTML = `
      <div class="cartao"><div class="num">${d.total}</div><div class="rot">fichas no mes</div></div>
      <div class="cartao"><div class="num">${d.qualidade}%</div><div class="rot">com proximo passo</div></div>
      <div class="cartao"><div class="num">${d.clientes}</div><div class="rot">clientes tocados</div></div>
      <div class="cartao"><div class="num">${d.municipios}</div><div class="rot">municipios</div></div>`;
    const linhas = Object.entries(d.por_tipo || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join('');
    const niveis = Object.entries(d.por_nivel || {}).map(([k, v]) => `<tr><td>evidencia ${esc(k)}</td><td>${v}</td></tr>`).join('');
    det.innerHTML = linhas || niveis ? `<table>${linhas}${niveis}</table>` : '';
  } catch (e) {
    box.innerHTML = '<div class="vazio">Resumo indisponivel offline.</div>';
    det.innerHTML = '';
  }
}

/* -------------------------------------------------------------- inicializacao */
async function carregarCfg() {
  try {
    const r = await fetch('/api/bootstrap');
    if (r.ok) {
      CFG = await r.json();
      await cacheGravar('cfg', CFG);
    } else throw new Error();
  } catch (e) {
    const c = await cacheLer('cfg');
    if (c && c.valor) CFG = c.valor;
  }
  $('lista-clientes').innerHTML = (CFG.clientes || [])
    .map(c => `<option value="${esc(c.nome)}">`).join('');
  $('lista-municipios').innerHTML = (CFG.municipios || [])
    .map(m => `<option value="${esc(m)}">`).join('');

  // quem executa o proximo passo: sugere pessoas e areas reais, mas aceita
  // nome digitado - sempre vai faltar alguem na lista (terceiro, motorista...)
  const grupos = CFG.responsaveis || {};
  const nomes = Object.entries(grupos).flatMap(([grupo, lista]) =>
    lista.map(n => ({ nome: n, grupo })));
  const dl = $('lista-responsaveis');
  if (dl) dl.innerHTML = nomes
    .map(x => `<option value="${esc(x.nome)}">${esc(x.grupo)}</option>`).join('');
}

function recuperarRascunho() {
  const cru = localStorage.getItem('rascunho');
  if (!cru) return;
  try {
    const r = JSON.parse(cru);
    if (!r.tipo) return;
    const botao = document.querySelector(`.cartao-tipo[data-tipo="${r.tipo}"]`);
    if (!botao) return;
    botao.click();
    $('f-cliente').value = r.cliente || '';
    $('f-municipio').value = r.municipio || '';
    $('f-objetivo').value = r.objetivo || '';
    $('f-relato').value = r.relato || '';
    $('f-passo').value = r.passo || '';
    $('aviso-rascunho').classList.remove('oculto');
  } catch (e) { /* rascunho corrompido - ignora */ }
}

(async function iniciar() {
  await abrirBD();
  await carregarCfg();
  await atualizarStatus();
  recuperarRascunho();
  sincronizar();
  setInterval(sincronizar, 60000);
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
