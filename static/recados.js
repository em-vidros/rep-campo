/* REP Campo - recados do gestor para quem esta em campo */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ERROS = {
  texto_curto: 'Escreva o recado — pelo menos três letras.',
  sem_destinatario: 'Escolha para quem vai o recado.',
  nao_esta_pendente: 'Esse recado já foi concluído ou cancelado.',
};

let CLIENTES = [];

function msg(t, erro) {
  $('msg').innerHTML = t ? `<div class="alerta ${erro ? 'erro' : 'info'}">${esc(t)}</div>` : '';
}

const dataBr = iso => {
  if (!iso) return '';
  const d = String(iso).slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : iso;
};

/* ------------------------------------------------------------- carregar */

async function carregar() {
  const situacao = $('f-situacao').value;
  const r = await fetch('/api/recados?situacao=' + encodeURIComponent(situacao));
  if (!r.ok) return msg('Não consegui carregar os recados.', true);
  const d = await r.json();

  const sel = $('r-para');
  if (!sel.options.length) {
    sel.innerHTML = d.reps.map(u =>
      `<option value="${esc(u.login)}">${esc(u.nome)}</option>`).join('')
      || '<option value="">nenhum representante ativo</option>';
  }
  desenhar(d.recados);
}

function desenhar(lista) {
  if (!lista.length) {
    $('lista-recados').innerHTML = '<p class="dica">Nenhum recado aqui.</p>';
    return;
  }
  $('lista-recados').innerHTML = lista.map(r => {
    const pendente = r.status === 'aberto' || r.status === 'lido';
    const selo = { aberto: 'não lido', lido: 'lido', concluido: 'concluído',
                   cancelado: 'cancelado' }[r.status] || r.status;
    return `<article class="item-recado ${r.status}">
      <div class="linha-topo">
        <span class="selo ${r.status}">${esc(selo)}</span>
        ${r.cliente_nome ? `<b>${esc(r.cliente_nome)}</b>` : '<b>recado geral</b>'}
        ${r.prazo ? `<span class="dica">até ${esc(dataBr(r.prazo))}</span>` : ''}
      </div>
      <p class="texto">${esc(r.texto)}</p>
      <p class="dica">de ${esc(r.criado_por_nome)} · ${esc(dataBr(r.criado_em))}
        ${r.concluido_em ? ` · concluído em ${esc(dataBr(r.concluido_em))}` : ''}</p>
      ${r.resposta ? `<p class="resposta">Resposta dele: ${esc(r.resposta)}</p>` : ''}
      ${pendente ? `<button class="mini" data-cancelar="${r.id}">cancelar</button>` : ''}
    </article>`;
  }).join('');
}

/* -------------------------------------------------------------- mandar */

$('btn-mandar').addEventListener('click', async () => {
  const texto = $('r-texto').value.trim();
  if (texto.length < 3) return msg(ERROS.texto_curto, true);

  const escolhido = CLIENTES.find(c => rotulo(c) === $('r-cliente').value.trim());
  if ($('r-cliente').value.trim() && !escolhido) {
    return msg('Escolha o cliente na lista, ou deixe o campo vazio para recado geral.', true);
  }

  const r = await fetch('/api/recados', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      para: $('r-para').value, texto,
      cliente_codigo: escolhido ? escolhido.codigo : '',
      cliente_nome: escolhido ? escolhido.nome : '',
      prazo: $('r-prazo').value,
    }),
  });
  const d = await r.json();
  if (!r.ok) return msg(ERROS[d.erro] || 'Não consegui mandar o recado.', true);

  $('r-texto').value = ''; $('r-cliente').value = ''; $('r-prazo').value = '';
  msg(escolhido ? 'Missão criada. Ela aparece para ele na sugestão de visitas e na ficha desse cliente.'
                : 'Recado mandado. Ele vê na faixa do topo do app.');
  carregar();
});

$('lista-recados').addEventListener('click', async ev => {
  const b = ev.target.closest('[data-cancelar]');
  if (!b) return;
  if (!confirm('Cancelar este recado? Ele deixa de aparecer para o representante.')) return;
  const r = await fetch(`/api/recados/${b.dataset.cancelar}/cancelar`, { method: 'POST' });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) return msg(ERROS[d.erro] || 'Não consegui cancelar.', true);
  msg('Recado cancelado.');
  carregar();
});

$('f-situacao').addEventListener('change', carregar);

/* ------------------------------------------------------------- clientes */

const rotulo = c => `${c.nome} — ${c.cidade || 'sem cidade'}`;

async function carregarClientes() {
  const r = await fetch('/api/bootstrap');
  if (!r.ok) return;
  const d = await r.json();
  CLIENTES = d.clientes || [];
  $('lista-clientes').innerHTML = CLIENTES
    .map(c => `<option value="${esc(rotulo(c))}">`).join('');
}

carregarClientes();
carregar();
