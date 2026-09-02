/* REP Campo - importar a planilha de rotas pela tela */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ERROS = {
  arquivo_ausente: 'Escolha a planilha antes de enviar.',
  arquivo_grande: 'A planilha passa de 6 MB.',
  nao_e_planilha: 'Não consegui ler o arquivo como planilha .xlsx.',
  sem_coluna_cidade: 'A planilha não tem a coluna CIDADE.',
  planilha_vazia: 'A planilha não tem linhas de cidade.',
  importe_a_planilha_antes: 'Envie a planilha primeiro.',
};

function msg(t, erro) {
  $('msg').innerHTML = `<div class="alerta ${erro ? 'erro' : 'info'}">${esc(t)}</div>`;
}

$('form-rotas').addEventListener('submit', async ev => {
  ev.preventDefault();
  const arq = $('f-planilha').files[0];
  if (!arq) return msg('Escolha a planilha.', true);
  msg('Lendo a planilha…');

  const fd = new FormData();
  fd.append('arquivo', arq);
  const r = await fetch('/api/importar/rotas', { method: 'POST', body: fd });
  const d = await r.json();
  if (!r.ok) return msg(ERROS[d.erro] || 'Não foi possível ler a planilha.', true);

  msg('Planilha lida.');
  $('resultado-envio').innerHTML = `
    <div class="cartoes-larg" style="margin-top:14px">
      <div class="cartao"><div class="num">${d.cidades}</div><div class="rot">cidades na planilha</div></div>
      <div class="cartao"><div class="num">${d.base_itz}</div><div class="rot">da base Imperatriz</div></div>
      <div class="cartao"><div class="num">${d.rotas.length}</div><div class="rot">rotas</div></div>
    </div>
    <p class="explica">Rotas encontradas: <b>${d.rotas.map(esc).join(' · ')}</b></p>`;
  $('passo-aplicar').classList.remove('oculto');
  $('passo-aplicar').scrollIntoView({ behavior: 'smooth', block: 'center' });
});

$('btn-aplicar').onclick = async () => {
  if (!confirm('Aplicar as rotas da planilha à carteira?\n\nNenhum cliente é apagado — só a rota e a tabela de preço mudam.')) return;
  msg('Aplicando…');
  const r = await fetch('/api/importar/aplicar-rotas', { method: 'POST' });
  const d = await r.json();
  if (!r.ok) return msg(ERROS[d.erro] || 'Não foi possível aplicar.', true);

  msg(d.corrigidos + ' cliente(s) tiveram a rota corrigida.');
  $('resultado-aplicar').innerHTML = `
    <div class="cartao-form" style="margin-top:18px">
      <h3 style="margin-top:0">O que mudou</h3>
      ${d.resumo.length ? `<div class="tabela-rolagem"><table>
        <thead><tr><th>De</th><th>Para</th><th class="num">Clientes</th></tr></thead>
        <tbody>${d.resumo.map(x => `<tr><td>${esc(x.de)}</td><td><b>${esc(x.para)}</b></td>
          <td class="num">${x.clientes}</td></tr>`).join('')}</tbody></table></div>`
        : '<p class="explica">Nenhuma rota precisou mudar — a carteira já batia com a planilha.</p>'}

      ${d.total_fora ? `<h3>${d.total_fora} cidade(s) fora da planilha</h3>
        <p class="explica">A rota que veio da carteira foi mantida. Se elas devem ter
          rota, o lugar de corrigir é a planilha — não aqui.</p>
        <p style="font-size:.85rem">${d.fora_da_planilha.map(esc).join(' · ')}</p>` : ''}

      ${d.de_outra_base.length ? `<h3>${d.de_outra_base.length} cidade(s) de outra base</h3>
        <p class="explica">A planilha diz que quem atende é a Raposa. Ficam na carteira,
          mas fora do planejamento — provável falha de cadastro.</p>
        <p style="font-size:.85rem">${d.de_outra_base.map(esc).join(' · ')}</p>` : ''}
    </div>`;
};
