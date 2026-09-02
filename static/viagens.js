/* REP Campo - planejamento de viagem e sugestao de visitas */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const brl = v => (v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const dataBR = iso => { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleDateString('pt-BR'); };

let sugeridos = [], escolhidos = new Set();
let ROTAS = [], cidadesMarcadas = new Set(), avulsas = new Map();

function msg(t, erro) {
  $('msg').innerHTML = `<div class="alerta ${erro ? 'erro' : 'info'}">${esc(t)}</div>`;
  setTimeout(() => { $('msg').innerHTML = ''; }, 4000);
}

document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'lista') carregarViagens();
carregarRotas();
});

/* ---------------------------------------------------------------- rotas */
async function carregarRotas() {
  const r = await fetch('/api/rotas');
  if (!r.ok) return;
  const d = await r.json();
  ROTAS = d.rotas;
  $('v-rota').innerHTML = '<option value="">selecione a rota</option>' +
    ROTAS.map(x => `<option value="${esc(x.rota)}">${esc(x.rota)}</option>`).join('');

  // todas as cidades, para a de passagem - mostra a rota de origem
  const todas = ROTAS.flatMap(r => r.cidades.map(c => ({ ...c, rota: r.rota })));
  todas.sort((a, b) => a.cidade.localeCompare(b.cidade, 'pt-BR'));
  $('todas-cidades').innerHTML = todas
    .map(c => `<option value="${esc(c.cidade)}">${esc(c.rota)} · ${c.clientes} cliente(s)</option>`).join('');
  window.TODAS_CIDADES = todas;
}

$('v-rota').onchange = () => {
  const rota = ROTAS.find(x => x.rota === $('v-rota').value);
  cidadesMarcadas = new Set();
  avulsas = new Map();
  $('box-cidades').classList.toggle('oculto', !rota);
  if (!rota) return desenharChips(null);
  rota.cidades.forEach(c => cidadesMarcadas.add(c.cidade));   // começa com tudo
  desenharChips(rota);
};

function desenharChips(rota) {
  if (!rota) { $('chips-cidades').innerHTML = ''; $('resumo-cidades').textContent = ''; return; }
  const daRota = rota.cidades.map(c => `
    <button type="button" class="chip ${cidadesMarcadas.has(c.cidade) ? 'on' : ''}"
            data-cidade="${esc(c.cidade)}">
      ${esc(c.cidade)} <span>${c.clientes}</span>
    </button>`).join('');
  const extras = [...avulsas.values()].map(c => `
    <button type="button" class="chip passagem ${cidadesMarcadas.has(c.cidade) ? 'on' : ''}"
            data-cidade="${esc(c.cidade)}" title="de passagem — rota ${esc(c.rota)}">
      ${esc(c.cidade)} <span>${c.clientes}</span>
      <b class="tira" data-tirar="${esc(c.cidade)}">×</b>
    </button>`).join('');
  $('chips-cidades').innerHTML = daRota + extras;

  $('chips-cidades').querySelectorAll('.chip').forEach(b => b.onclick = ev => {
    if (ev.target.dataset.tirar) {
      avulsas.delete(ev.target.dataset.tirar);
      cidadesMarcadas.delete(ev.target.dataset.tirar);
      return desenharChips(rota);
    }
    const cid = b.dataset.cidade;
    cidadesMarcadas.has(cid) ? cidadesMarcadas.delete(cid) : cidadesMarcadas.add(cid);
    desenharChips(rota);
  });

  const marcadas = rota.cidades.concat([...avulsas.values()])
    .filter(c => cidadesMarcadas.has(c.cidade));
  const total = marcadas.reduce((s, c) => s + c.clientes, 0);
  const nPass = [...avulsas.keys()].filter(c => cidadesMarcadas.has(c)).length;
  $('resumo-cidades').textContent =
    `${marcadas.length} cidade(s)${nPass ? ' (' + nPass + ' de passagem)' : ''} · ${total} cliente(s) na carteira`;
}

/* cidade de passagem: cliente fora da rota que fica no caminho */
$('btn-add-cidade').onclick = () => {
  const nome = $('cidade-avulsa').value.trim();
  if (!nome) return;
  const achada = (window.TODAS_CIDADES || []).find(c => c.cidade === nome);
  if (!achada) return msg('Cidade não encontrada na carteira.', true);
  const rota = ROTAS.find(x => x.rota === $('v-rota').value);
  if (rota && rota.cidades.some(c => c.cidade === nome))
    return msg('Essa cidade já está na rota escolhida.', true);
  avulsas.set(nome, achada);
  cidadesMarcadas.add(nome);
  $('cidade-avulsa').value = '';
  desenharChips(rota);
};
$('cidade-avulsa').addEventListener('keydown', ev => {
  if (ev.key === 'Enter') { ev.preventDefault(); $('btn-add-cidade').click(); }
});

$('btn-todas').onclick = () => {
  const rota = ROTAS.find(x => x.rota === $('v-rota').value);
  if (!rota) return;
  rota.cidades.forEach(c => cidadesMarcadas.add(c.cidade));
  desenharChips(rota);
};
$('btn-nenhuma').onclick = () => {
  const rota = ROTAS.find(x => x.rota === $('v-rota').value);
  cidadesMarcadas = new Set();
  desenharChips(rota);
};

/* ------------------------------------------------------------- sugestao */
async function buscarSugestao() {
  if (!cidadesMarcadas.size) {
    $('aviso-filtro').textContent = 'Escolha a rota e marque ao menos uma cidade.';
    return;
  }
  $('aviso-filtro').textContent = '';
  const q = new URLSearchParams();
  q.set('cidades', [...cidadesMarcadas].join('|'));
  q.set('limite', '120');
  const r = await fetch('/api/sugestao?' + q);
  if (!r.ok) return msg('Não foi possível buscar.', true);
  const d = await r.json();
  sugeridos = d.clientes;

  $('lista-sugestao').innerHTML = sugeridos.map((c, i) => `
    <div class="ficha sugestao ${escolhidos.has(c.codigo) ? 'escolhido' : ''}" data-i="${i}">
      <div class="ficha-cab">
        <div>
          <b>${esc(c.nome)}</b>
          <div class="sub">${esc(c.cidade || '—')}${c.rota ? ' · ' + esc(c.rota) : ''}
            · ${c.curva ? 'curva ' + esc(c.curva) : 'sem curva'} · ${brl(c.vol_12m)}
            ${c.vendedor ? ' · ' + esc(c.vendedor) : ''}</div>
          <div class="motivo">${esc(c.motivo)}</div>
        </div>
        <div class="ficha-selos">
          ${c.oc_abertas ? '<span class="selo pendente">ocorrência aberta</span>' : ''}
          ${c.pior_nota !== null && c.pior_nota <= 6 ? `<span class="selo media">nota ${c.pior_nota}</span>` : ''}
          <button class="btn-sec" data-add="${i}">${escolhidos.has(c.codigo) ? 'remover' : 'incluir'}</button>
        </div>
      </div>
    </div>`).join('') ||
    '<div class="vazio">Nenhum cliente precisando de visita com esse filtro.</div>';

  document.querySelectorAll('[data-add]').forEach(b => b.onclick = () => {
    const c = sugeridos[b.dataset.add];
    escolhidos.has(c.codigo) ? escolhidos.delete(c.codigo) : escolhidos.add(c.codigo);
    buscarSugestao();
  });
  atualizarRodape();
}

function atualizarRodape() {
  const n = escolhidos.size;
  $('rodape-plano').classList.toggle('oculto', n === 0);
  $('conta-selecao').textContent = n + (n === 1 ? ' cliente no roteiro' : ' clientes no roteiro');
}

$('s-buscar').onclick = buscarSugestao;

/* -------------------------------------------------------------- criar */
$('btn-criar').onclick = async () => {
  const nome = $('v-nome').value.trim();
  if (!nome) { msg('Dê um nome para a viagem.', true); $('v-nome').focus(); return; }
  const r = await fetch('/api/viagens', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nome, rota: $('v-rota').value, inicio: $('v-inicio').value,
      fim: $('v-fim').value, observacao: $('v-obs').value.trim() }) });
  const j = await r.json();
  if (!r.ok) return msg('Não foi possível criar a viagem.', true);

  const escolha = sugeridos.filter(c => escolhidos.has(c.codigo));
  await fetch('/api/viagens/' + j.id + '/clientes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clientes: escolha }) });

  msg('Viagem criada com ' + escolha.length + ' cliente(s).');
  escolhidos = new Set(); cidadesMarcadas = new Set(); avulsas = new Map();
  $('form-viagem').reset(); $('lista-sugestao').innerHTML = '';
  $('box-cidades').classList.add('oculto');
  atualizarRodape();
  document.querySelector('.aba[data-tela="lista"]').click();
};

/* ------------------------------------------------------------- viagens */
async function carregarViagens() {
  const r = await fetch('/api/viagens');
  if (!r.ok) return;
  const d = await r.json();
  $('lista-viagens').innerHTML = d.viagens.map(v => `
    <div class="ficha">
      <div class="ficha-cab" data-abrir="${v.id}">
        <div><b>${esc(v.nome)}</b>
          <div class="sub">${v.inicio ? dataBR(v.inicio) : 'sem data'}${v.fim ? ' a ' + dataBR(v.fim) : ''}
            ${v.rota ? ' · ' + esc(v.rota) : ''} · ${v.planejados} cliente(s)
            ${v.responsavel ? ' · ' + esc(v.responsavel) : ''}</div></div>
        <div class="ficha-selos">
          <span class="selo ${v.aderencia >= 80 ? 'forte' : v.aderencia >= 50 ? 'media' : 'pendente'}">
            ${v.visitados}/${v.planejados} visitados${v.aderencia !== null ? ' · ' + v.aderencia + '%' : ''}</span>
          <span class="selo leve">${esc(v.status)}</span>
        </div>
      </div>
      <div class="ficha-corpo" id="corpo-${v.id}"></div>
    </div>`).join('') || '<div class="vazio">Nenhuma viagem planejada ainda.</div>';

  document.querySelectorAll('[data-abrir]').forEach(c => c.onclick = async () => {
    const ficha = c.parentElement;
    ficha.classList.toggle('aberta');
    if (!ficha.classList.contains('aberta')) return;
    const id = c.dataset.abrir;
    const r = await fetch('/api/viagens/' + id);
    const v = await r.json();
    $('corpo-' + id).innerHTML = `
      ${v.observacao ? `<div class="bloco"><h4>Observação</h4><p>${esc(v.observacao)}</p></div>` : ''}
      <div class="bloco"><h4>Roteiro</h4>
        ${v.clientes.map(c => `
          <div class="item-roteiro ${c.visitado ? 'feito' : ''}">
            <span class="marca-visita">${c.visitado ? '✓' : '○'}</span>
            <div><b>${esc(c.cliente_nome)}</b>
              <div class="sub">${esc(c.municipio || '—')}${c.motivo ? ' · ' + esc(c.motivo) : ''}
                ${c.visitado ? ' · visitado em ' + dataBR(c.visitado_em) : ''}</div></div>
          </div>`).join('') || '<p class="explica">Sem clientes no roteiro.</p>'}
      </div>
      <div class="bloco"><h4>Situação</h4>
        <select data-status="${id}">
          ${['planejada', 'em_andamento', 'concluida'].map(st =>
            `<option value="${st}"${st === v.status ? ' selected' : ''}>${st.replace('_', ' ')}</option>`).join('')}
        </select></div>`;
    $('corpo-' + id).querySelector('[data-status]').onchange = async ev => {
      await fetch('/api/viagens/' + id, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: ev.target.value }) });
      msg('Situação atualizada.');
    };
  });
}

carregarViagens();
carregarRotas();
