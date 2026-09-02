/* REP Campo - planejamento de viagem e sugestao de visitas */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const brl = v => (v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const dataBR = iso => { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleDateString('pt-BR'); };

let sugeridos = [], escolhidos = new Set();

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
});

/* ------------------------------------------------------------- sugestao */
async function buscarSugestao() {
  const q = new URLSearchParams();
  if ($('s-municipio').value.trim()) q.set('municipio', $('s-municipio').value.trim());
  if ($('s-rota').value.trim()) q.set('rota', $('s-rota').value.trim());
  const r = await fetch('/api/sugestao?' + q);
  if (!r.ok) return msg('Não foi possível buscar.', true);
  const d = await r.json();
  sugeridos = d.clientes;

  $('s-lista-mun').innerHTML = d.municipios.map(m => `<option value="${esc(m)}">`).join('');
  $('s-lista-rota').innerHTML = d.rotas.map(m => `<option value="${esc(m)}">`).join('');

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
      nome, rota: $('v-rota').value.trim(), inicio: $('v-inicio').value,
      fim: $('v-fim').value, observacao: $('v-obs').value.trim() }) });
  const j = await r.json();
  if (!r.ok) return msg('Não foi possível criar a viagem.', true);

  const escolha = sugeridos.filter(c => escolhidos.has(c.codigo));
  await fetch('/api/viagens/' + j.id + '/clientes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clientes: escolha }) });

  msg('Viagem criada com ' + escolha.length + ' cliente(s).');
  escolhidos = new Set(); $('form-viagem').reset(); $('lista-sugestao').innerHTML = '';
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
