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

/* --------------------------------------------------------------- sem rede */
// Leitura passa pelo service worker, que devolve a copia da ultima vez que a
// tela abriu com sinal. Quando nem isso existe, `pegar` volta null e quem
// chamou escreve na tela o motivo, em vez de deixar em branco.
// navigator.onLine mente numa pagina aberta pelo cache: diz "online" sem rede
// nenhuma. Entao quem manda aqui e o que a ultima chamada de verdade mostrou.
let redeCaiu = false;
const semRede = () => !navigator.onLine || redeCaiu;

async function pegar(url) {
  try {
    const r = await fetch(url);
    redeCaiu = r.headers.get('X-Rep-Cache') === '1';
    marcarConexao();
    return r.ok ? await r.json() : null;
  } catch (e) {
    redeCaiu = true;
    marcarConexao();
    return null;
  }
}

// Planejar e mudar situacao mexem no banco. Sem rede nao da, e o REP precisa
// ouvir isso na hora - nao existe fila de viagem como existe de ficha.
function exigeRede(acao) {
  if (!semRede()) return true;
  msg('Sem internet: ' + acao + ' só funciona com sinal. O roteiro que você já '
      + 'tem continua à vista.', true);
  return false;
}

function marcarConexao() {
  const b = $('faixa-offline');
  if (b) b.classList.toggle('oculto', !semRede());
}
// A pagina aberta pelo cache se acha online e nunca dispara 'online'. Sem a
// sonda a faixa ficaria na tela depois que o sinal voltasse.
async function sondarRede() {
  const antes = redeCaiu;
  try { await fetch('/ping', { cache: 'no-store' }); redeCaiu = false; }
  catch (e) { redeCaiu = true; }
  marcarConexao();
  if (antes && !redeCaiu) { carregarViagens(); carregarRotas(); }
}
setInterval(() => { if (semRede()) sondarRede(); }, 60000);

window.addEventListener('online', () => {
  redeCaiu = false;
  marcarConexao();
  carregarViagens();
  carregarRotas();
});
window.addEventListener('offline', () => { redeCaiu = true; marcarConexao(); });

document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'lista') carregarViagens();
  if (b.dataset.tela === 'avulsas') carregarAvulsas();
  if (b.dataset.tela === 'planejar') carregarRotas();
});

/* ---------------------------------------------------------------- rotas */
async function carregarRotas() {
  const d = await pegar('/api/rotas');
  if (!d) return;
  ROTAS = d.rotas;
  // avisa sobre cadastro de outra base, sem esconder o problema
  if (d.clientes_fora) {
    const quais = [...new Set(d.fora_da_base.map(x => x.rota))].join(', ');
    $('msg').innerHTML = `<div class="alerta info">${d.clientes_fora} cliente(s) na carteira
      com rota de outra base (${esc(quais)}) ficaram fora do planejamento — provável
      falha de cadastro. Continuam na carteira; só não são sugeridos.</div>`;
  }
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
  if ($('s-parados').checked) q.set('parados', '1');
  if (!exigeRede('montar a sugestão de clientes')) return;
  const d = await pegar('/api/sugestao?' + q);
  if (!d) return msg('Não foi possível buscar.', true);
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
          ${c.dias_sem_comprar > 30 ? `<span class="selo pendente">sem comprar há ${c.dias_sem_comprar}d</span>` : ''}
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
  if (!exigeRede('criar viagem')) return;
  const r = await fetch('/api/viagens', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nome, rota: $('v-rota').value, tipo: $('v-tipo').value,
      inicio: $('v-inicio').value,
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
  marcarConexao();
  const d = await pegar('/api/viagens');
  if (!d) {
    $('lista-viagens').innerHTML = '<div class="vazio">Sem internet e sem cópia '
      + 'guardada. Abra esta tela uma vez com sinal e ela passa a funcionar '
      + 'offline.</div>';
    return;
  }
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
    const v = await pegar('/api/viagens/' + id);
    if (!v) {
      $('corpo-' + id).innerHTML = '<div class="vazio">Sem internet e sem cópia '
        + 'deste roteiro. Abra a viagem uma vez com sinal.</div>';
      return;
    }
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
      <div class="bloco">
        <button type="button" class="btn-sec" data-relatorio="${id}">Ver relatório da viagem</button>
      </div>
      <div id="relatorio-${id}"></div>
      <div class="bloco"><h4>Situação</h4>
        <select data-status="${id}">
          ${['planejada', 'em_andamento', 'concluida'].map(st =>
            `<option value="${st}"${st === v.status ? ' selected' : ''}>${st.replace('_', ' ')}</option>`).join('')}
        </select></div>`;
    const btnRel = $('corpo-' + id).querySelector('[data-relatorio]');
    if (btnRel) btnRel.onclick = () => verRelatorio(id, $('relatorio-' + id));
    $('corpo-' + id).querySelector('[data-status]').onchange = async ev => {
      if (!exigeRede('mudar a situação da viagem')) { ev.target.value = v.status; return; }
      await fetch('/api/viagens/' + id, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: ev.target.value }) });
      msg('Situação atualizada.');
    };
  });
}

carregarViagens();
carregarRotas();


/* ------------------------------------------------- relatorio da viagem */
async function verRelatorio(id, alvo) {
  const d = await pegar('/api/viagens/' + id + '/relatorio');
  if (!d) return msg('Não foi possível montar o relatório.', true);
  const v = d.viagem;
  const linha = (rot, val) => `<div class="cc-linha"><span>${esc(rot)}</span><b>${val}</b></div>`;

  alvo.innerHTML = `
    <div class="relatorio">
      <h3>Relatório — ${esc(v.nome)}</h3>
      <p class="explica">${v.inicio ? dataBR(v.inicio) : 'sem data'}${v.fim ? ' a ' + dataBR(v.fim) : ''}
        ${v.rota ? ' · rota ' + esc(v.rota) : ''} · ${esc(v.responsavel || v.criada_por)}</p>

      <div class="cartoes-larg">
        <div class="cartao"><div class="num">${d.visitados}/${d.planejados}</div>
          <div class="rot">visitados${d.aderencia !== null ? ' · ' + d.aderencia + '%' : ''}</div></div>
        <div class="cartao"><div class="num">${d.fichas.length}</div><div class="rot">fichas</div></div>
        <div class="cartao"><div class="num ${d.ocorrencias.length ? 'num-alerta' : ''}">${d.ocorrencias.length}</div>
          <div class="rot">ocorrências abertas</div></div>
        <div class="cartao"><div class="num">${d.media_pesquisa === null ? '—' : d.media_pesquisa}</div>
          <div class="rot">nota média · ${d.clientes_ouvidos} ouvido(s)</div></div>
      </div>

      ${Object.keys(d.por_tipo).length ? `<div class="bloco"><h4>Visitas por tipo</h4>
        ${Object.entries(d.por_tipo).map(([t, n]) => linha(t, n)).join('')}</div>` : ''}

      ${d.municipios.length ? `<div class="bloco"><h4>Municípios percorridos</h4>
        ${d.municipios.map(([m, n]) => linha(m, n + ' visita(s)')).join('')}</div>` : ''}

      ${d.ocorrencias.length ? `<div class="bloco"><h4>Ocorrências abertas na viagem</h4>
        ${d.ocorrencias.map(o => `<div class="item-roteiro"><span class="marca-visita">!</span>
          <div><b>${esc(o.numero)} · ${esc(o.cliente_nome)}</b>
          <div class="sub">${esc(o.tipo || '—')} · ${esc(o.status)}${o.responsavel ? ' · ' + esc(o.responsavel) : ''}</div>
          </div></div>`).join('')}</div>` : ''}

      ${d.encaminhamentos.length ? `<div class="bloco"><h4>Encaminhados ao time</h4>
        ${d.encaminhamentos.map(f => `<div class="item-roteiro"><span class="marca-visita">→</span>
          <div><b>${esc(f.cliente_nome)}</b>
          <div class="sub">para ${esc(f.encaminhado_para)} · ${esc(f.proximo_passo || '')}</div>
          </div></div>`).join('')}</div>` : ''}

      ${d.respostas.length ? `<div class="bloco"><h4>Pesquisa coletada</h4>
        ${d.respostas.map(x => `<div class="cc-linha">
          <span>${esc(x.etapa)}${x.unidade ? ' (' + esc(x.unidade) + ')' : ''}</span>
          <b>${x.nota}</b></div>`).join('')}</div>` : ''}

      ${d.fora_do_roteiro.length ? `<div class="bloco"><h4>Visitados fora do roteiro</h4>
        ${d.fora_do_roteiro.map(f => `<div class="item-roteiro"><span class="marca-visita">+</span>
          <div><b>${esc(f.cliente_nome)}</b><div class="sub">${esc(f.municipio || '')}</div></div>
          </div>`).join('')}</div>` : ''}

      ${d.nao_visitados.length ? `<div class="bloco"><h4>Não visitados</h4>
        ${d.nao_visitados.map(c => `<div class="item-roteiro"><span class="marca-visita">○</span>
          <div><b>${esc(c.cliente_nome)}</b><div class="sub">${esc(c.municipio || '')}${c.motivo ? ' · ' + esc(c.motivo) : ''}</div></div>
          </div>`).join('')}</div>` : ''}

      <button type="button" class="btn-sec" onclick="window.print()">Imprimir</button>
    </div>`;
}

/* ------------------------------------------------- visitas sem viagem */
async function carregarAvulsas() {
  const d = await pegar('/api/visitas-avulsas');
  if (!d) {
    $('lista-avulsas').innerHTML = '<div class="vazio">Sem internet e sem cópia '
      + 'guardada desta tela.</div>';
    return;
  }
  $('cartoes-avulsas').innerHTML = `
    <div class="cartao"><div class="num">${d.total}</div><div class="rot">visitas no mês</div></div>
    <div class="cartao"><div class="num">${d.clientes}</div><div class="rot">clientes</div></div>
    <div class="cartao"><div class="num">${d.por_municipio.length}</div><div class="rot">municípios</div></div>`;
  $('lista-avulsas').innerHTML = (d.fichas.length ? `
    <div class="ficha"><div class="ficha-corpo" style="display:block">
      <div class="bloco"><h4>Por município</h4>
        ${d.por_municipio.map(([m, n]) => `<div class="cc-linha"><span>${esc(m)}</span><b>${n}</b></div>`).join('')}</div>
      <div class="bloco"><h4>Visitas</h4>
        ${d.fichas.map(f => `<div class="item-roteiro"><span class="marca-visita">·</span>
          <div><b>${esc(f.cliente_nome)}</b>
          <div class="sub">${esc(f.tipo)} · ${esc(f.municipio || '—')} · ${dataBR(f.recebido_em)}
          ${f.proximo_passo ? ' · ' + esc(f.proximo_passo) : ''}</div></div></div>`).join('')}</div>
    </div></div>` : '<div class="vazio">Nenhuma visita avulsa neste mês.</div>');
}
