/* REP Campo - comparacao de preco da concorrencia */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const brl = v => (v || 0).toLocaleString('pt-BR',
  { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const dataBr = iso => {
  if (!iso) return '';
  const d = String(iso).slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : iso;
};

/* Preco velho engana quem negocia: a cor diz se aquilo ainda vale. */
function idade(iso) {
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 30) return { dias, classe: 'fresco' };
  if (dias <= 90) return { dias, classe: 'morno' };
  return { dias, classe: 'velho' };
}

let PRIMEIRA = true;

async function carregar() {
  const q = new URLSearchParams({
    rota: $('f-rota').value, municipio: $('f-municipio').value,
    cliente: $('f-cliente').value, desde: $('f-desde').value,
  });
  const r = await fetch('/api/precos/matriz?' + q);
  if (r.status === 403) return;          // representante nao ve a grade
  if (!r.ok) {
    $('msg').innerHTML = '<div class="alerta erro">Não consegui carregar os preços.</div>';
    return;
  }
  const d = await r.json();
  if (PRIMEIRA) { encherFiltros(d.recortes); PRIMEIRA = false; }
  desenhar(d);
}

function encherFiltros(rec) {
  const opc = (sel, itens, valor, texto) => {
    const e = $(sel), primeira = e.options[0].outerHTML;
    e.innerHTML = primeira + itens.map(x =>
      `<option value="${esc(valor(x))}">${esc(texto(x))}</option>`).join('');
  };
  opc('f-rota', rec.rotas, x => x, x => x);
  opc('f-municipio', rec.municipios, x => x, x => x);
  opc('f-cliente', rec.clientes, x => x.codigo, x => x.nome || x.codigo);
}

function desenhar(d) {
  const alvo = $('grade-precos');
  if (!d.concorrentes.length) {
    alvo.innerHTML = '<p class="dica">Nenhum preço pesquisado neste recorte. '
      + 'Os preços entram sozinhos quando o representante salva uma ficha do tipo '
      + '<b>Preço</b>.</p>';
    $('resumo-grade').textContent = '';
    return;
  }
  $('resumo-grade').innerHTML =
    `<b>${d.concorrentes.length}</b> concorrente(s) &middot; `
    + `<b>${d.coletas}</b> preço(s) neste recorte`;

  const cab = d.concorrentes.map(c => `<th>${esc(c)}</th>`).join('');

  const corpo = d.grupos.map(g => {
    const linhas = g.itens.map(it => {
      const celulas = d.concorrentes.map(c => {
        const v = it.precos[c];
        if (!v) return '<td class="vazia">—</td>';
        const i = idade(v.coletado_em);
        const dica = `${dataBr(v.coletado_em)} · ${v.municipio || 'sem cidade'}`
          + ` · ${i.dias} dias · por ${v.por}`
          + (v.observacao ? `\n${v.observacao}` : '');
        return `<td class="celula ${i.classe}" title="${esc(dica)}">
          <b>${esc(brl(v.preco))}</b><small>${i.dias} d</small></td>`;
      }).join('');
      return `<tr><th class="item">${esc(it.item)}</th>${celulas}</tr>`;
    }).join('');
    return `<tr class="grupo"><th colspan="${d.concorrentes.length + 1}">${esc(g.grupo)}</th></tr>${linhas}`;
  }).join('');

  alvo.innerHTML = `<div class="rolagem"><table class="grade">
    <thead><tr><th class="item">Item</th>${cab}</tr></thead>
    <tbody>${corpo}</tbody></table></div>`;
}

/* ------------------------------------------------------------ onde atua */

async function carregarAtuacao() {
  const r = await fetch('/api/precos/onde-atua');
  if (!r.ok) return;
  const d = await r.json();
  if (!d.concorrentes.length) {
    $('lista-atuacao').innerHTML = '<p class="dica">Ainda não há pesquisa de preço registrada.</p>';
    return;
  }
  $('lista-atuacao').innerHTML = d.concorrentes.map(c => `
    <section class="cartao">
      <h2>${esc(c.concorrente)} <span class="dica">${c.coletas} coleta(s)</span></h2>
      <div class="chips">${c.lugares.map(l =>
        `<span class="chip-lugar">${esc(l.municipio)}
          <small>${esc(l.rota)} · visto em ${esc(dataBr(l.visto_em))}</small></span>`).join('')}
      </div>
    </section>`).join('');
}

/* --------------------------------------------------------------- telas */

document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'atuacao') carregarAtuacao();
});

['f-rota', 'f-municipio', 'f-cliente', 'f-desde']
  .forEach(id => $(id).addEventListener('change', carregar));

$('btn-limpar').onclick = () => {
  ['f-rota', 'f-municipio', 'f-cliente', 'f-desde'].forEach(id => ($(id).value = ''));
  carregar();
};

if (document.getElementById('tela-grade')) carregar();

/* ==================================================== atualizar precos ====

   O representante consegue essa informacao a conta-gotas: uma proposta que o
   cliente mostrou, um telefonema, uma conversa na loja. E o mesmo preco quase
   nunca vale para uma cidade so - o concorrente pratica a mesma tabela na rota
   inteira, ou em parte dela mais alguma cidade vizinha de outra rota.
*/
let ROTAS = null;
const CIDADES = new Set();

const ERROS_P = {
  sem_concorrente: 'Escolha o concorrente.',
  sem_cidades: 'Marque ao menos uma cidade que esse preço cobre.',
  sem_precos: 'Preencha ao menos um preço.',
};

function msg(t, erro) {
  $('msg').innerHTML = t ? `<div class="alerta ${erro ? 'erro' : 'info'}">${esc(t)}</div>` : '';
  if (t) window.scrollTo({ top: 0, behavior: 'smooth' });
}

const concorrenteEscolhido = () =>
  $('p-concorrente').value === 'Outro' ? $('p-outro').value.trim() : $('p-concorrente').value;

async function carregarForm() {
  const q = new URLSearchParams({
    concorrente: concorrenteEscolhido() || '',
    cidades: [...CIDADES].join('|'),
  });
  const r = await fetch('/api/precos/formulario?' + q);
  if (!r.ok) return;
  const d = await r.json();

  if (!ROTAS) {
    ROTAS = d.rotas;
    $('p-concorrente').innerHTML = '<option value="">escolha</option>' +
      d.concorrentes.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
    $('p-rota').innerHTML = '<option value="">escolha a rota</option>' +
      ROTAS.map(x => `<option value="${esc(x.rota)}">${esc(x.rota)}</option>`).join('');
  }
  $('p-obs').value = d.observacao || '';
  $('aviso-anterior').innerHTML = d.ja_pesquisado
    ? 'Já existe pesquisa deste concorrente nessas cidades — os campos vêm com o '
      + '<b>último preço conhecido</b>. Ajuste o que mudou e salve.'
    : (concorrenteEscolhido() && CIDADES.size
        ? 'Primeira pesquisa deste concorrente nessas cidades.' : '');
  desenharItens(d.itens);
}

/* ------------------------------------------------------------- cidades */

function desenharCidades() {
  const rota = ROTAS && ROTAS.find(r => r.rota === $('p-rota').value);
  if (!rota) {
    $('cidades-rota').innerHTML = '<p class="dica">Escolha uma rota acima.</p>';
    return;
  }
  $('cidades-rota').innerHTML = rota.cidades.map(c => `
    <label class="cid">
      <input type="checkbox" value="${esc(c.cidade)}"
        ${CIDADES.has(c.cidade) ? 'checked' : ''}> ${esc(c.cidade)}
    </label>`).join('');
}

/* As marcadas ficam visiveis fora da rota, senao ele troca de rota e perde de
   vista o que ja escolheu antes. */
function desenharMarcadas() {
  const n = CIDADES.size;
  $('marcadas').innerHTML = !n ? '' :
    `<div class="rot-marcadas">${n} cidade(s) cobertas por este preço</div>` +
    [...CIDADES].sort((a, b) => a.localeCompare(b, 'pt-BR')).map(c =>
      `<span class="chip-cid">${esc(c)}<button data-tirar="${esc(c)}">×</button></span>`).join('');
}

$('p-rota').addEventListener('change', desenharCidades);

$('cidades-rota').addEventListener('change', ev => {
  const c = ev.target.closest('input[type=checkbox]');
  if (!c) return;
  c.checked ? CIDADES.add(c.value) : CIDADES.delete(c.value);
  desenharMarcadas();
  carregarForm();
});

$('marcadas').addEventListener('click', ev => {
  const b = ev.target.closest('[data-tirar]');
  if (!b) return;
  CIDADES.delete(b.dataset.tirar);
  desenharMarcadas(); desenharCidades(); carregarForm();
});

$('btn-todas').onclick = () => {
  const rota = ROTAS && ROTAS.find(r => r.rota === $('p-rota').value);
  if (!rota) return msg('Escolha uma rota primeiro.', true);
  rota.cidades.forEach(c => CIDADES.add(c.cidade));
  desenharCidades(); desenharMarcadas(); carregarForm();
};

$('btn-limpar-cid').onclick = () => {
  CIDADES.clear(); desenharCidades(); desenharMarcadas(); carregarForm();
};

/* --------------------------------------------------------------- itens */

function desenharItens(itens) {
  if (!concorrenteEscolhido() || !CIDADES.size) {
    $('form-itens').innerHTML = '<p class="dica">Escolha o concorrente e as cidades acima.</p>';
    return;
  }
  let grupo = '';
  $('form-itens').innerHTML = itens.map(x => {
    const cab = x.grupo !== grupo ? `<div class="grupo-itens">${esc(x.grupo)}</div>` : '';
    grupo = x.grupo;
    const quando = x.coletado_em
      ? `<small class="quando">último: ${esc(dataBr(x.coletado_em))}</small>` : '';
    return cab + `<div class="linha-preco">
      <span class="nome">${esc(x.item)}${quando}</span>
      <input inputmode="decimal" placeholder="R$/m²" data-item="${esc(x.item)}"
             value="${x.preco != null ? esc(brl(x.preco)) : ''}">
    </div>`;
  }).join('') + `
    <div class="grupo-itens">Outro item</div>
    <div class="linha-preco">
      <input id="p-item-livre" placeholder="nome do item">
      <input id="p-preco-livre" inputmode="decimal" placeholder="R$/m²">
    </div>`;
}

$('p-concorrente').addEventListener('change', () => {
  $('wrap-outro').classList.toggle('oculto', $('p-concorrente').value !== 'Outro');
  carregarForm();
});
$('p-outro').addEventListener('change', carregarForm);

$('btn-salvar').addEventListener('click', async () => {
  const itens = [...document.querySelectorAll('[data-item]')]
    .map(i => ({ item: i.dataset.item, preco: i.value.trim() }))
    .filter(x => x.preco);
  const livre = $('p-item-livre'), precoLivre = $('p-preco-livre');
  if (livre && livre.value.trim() && precoLivre.value.trim()) {
    itens.push({ item: livre.value.trim(), preco: precoLivre.value.trim() });
  }
  const r = await fetch('/api/precos/registrar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      concorrente: $('p-concorrente').value, concorrente_outro: $('p-outro').value,
      cidades: [...CIDADES], itens, observacao: $('p-obs').value,
    }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) return msg(ERROS_P[d.erro] || 'Não consegui salvar.', true);
  msg(`${d.gravados} preço(s) de ${d.concorrente} salvos para ${d.cidades} cidade(s).`);
  carregarForm();
  PRIMEIRA = true;
});

carregarForm();
