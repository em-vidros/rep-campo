/* Botao de espiar a senha. Se aplica sozinho a todo input[type=password]
   da pagina - inclusive aos criados depois, como o do formulario de usuario. */
'use strict';
(function () {
  const OLHO = '\u{1F441}';          // olho
  const RISCADO = '\u{1F648}';       // macaco tapando os olhos

  function equipar(campo) {
    if (campo.dataset.comOlho) return;
    campo.dataset.comOlho = '1';

    const capa = document.createElement('span');
    capa.className = 'campo-senha';
    campo.parentNode.insertBefore(capa, campo);
    capa.appendChild(campo);

    const botao = document.createElement('button');
    botao.type = 'button';               // nunca submete o formulario
    botao.className = 'espiar';
    botao.textContent = OLHO;
    botao.title = 'Mostrar a senha';
    botao.setAttribute('aria-label', 'Mostrar a senha');
    capa.appendChild(botao);

    botao.addEventListener('click', () => {
      const vendo = campo.type === 'text';
      campo.type = vendo ? 'password' : 'text';
      botao.textContent = vendo ? OLHO : RISCADO;
      const rotulo = vendo ? 'Mostrar a senha' : 'Esconder a senha';
      botao.title = rotulo;
      botao.setAttribute('aria-label', rotulo);
      campo.focus();
    });

    // some da tela ao enviar - senha nao fica visivel depois do submit
    const form = campo.closest('form');
    if (form) form.addEventListener('submit', () => {
      campo.type = 'password';
      botao.textContent = OLHO;
    });
  }

  const varrer = () => document.querySelectorAll('input[type="password"]').forEach(equipar);
  document.addEventListener('DOMContentLoaded', varrer);
  varrer();
  // campos criados depois (tela de usuarios) tambem ganham o botao
  new MutationObserver(varrer).observe(document.documentElement,
    { childList: true, subtree: true });
})();
