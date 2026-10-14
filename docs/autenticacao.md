# Acesso ao SIG QuIIN

## Telas públicas

| Tela | Rota |
| --- | --- |
| Login | `/accounts/login/` |
| Cadastro | `/accounts/cadastro/` |
| Esqueceu a senha | `/accounts/esqueceu-senha/` |
| Confirmação da solicitação | `/accounts/esqueceu-senha/enviado/` |
| Redefinição | `/accounts/redefinir-senha/<uidb64>/<token>/` |
| Confirmação da nova senha | `/accounts/redefinir-senha/concluido/` |

Todas usam o fundo institucional, o painel translúcido e o rodapé responsivo.
O logo SENAI CIMATEC fornecido está em
`static/img/login/senai-cimatec-correto.png`; o componente compartilhado usa
essa mesma imagem no rodapé das páginas internas.

## Cadastro

O formulário solicita nome, usuário, e-mail, senha e confirmação da senha.
Valida campos obrigatórios, formato do e-mail, usuário/e-mail duplicados e a
política de senha configurada no Django. O e-mail é salvo em minúsculas.

Após o cadastro, o usuário volta ao login com uma mensagem de sucesso.
A senha é armazenada com o hash do Django. Novas contas são criadas sem
grupos, permissões administrativas ou vínculos com pilares; a administração
define os acessos pelo gerenciamento de usuários já existente.
O cadastro e o login geram registros de auditoria.

## Recuperação no protótipo local

1. Acesse **Esqueci minha senha** no login.
2. Informe o e-mail de uma conta ativa que tenha senha utilizável.
3. Leia a mensagem de recuperação no terminal onde o `runserver` está rodando.
4. Abra o link exibido na mensagem e informe a nova senha duas vezes.
5. Volte ao login e entre com a nova senha.

O backend padrão é `django.core.mail.backends.console.EmailBackend`, que
simula a entrega local imprimindo a mensagem. Ele não envia e-mails reais.
As contas demo sem e-mail precisam receber um e-mail no gerenciamento de
usuários para participar desse fluxo.

A confirmação da solicitação é igual para e-mails conhecidos e desconhecidos.
Links adulterados, expirados ou já utilizados não permitem alterar a senha.
O Django controla a validade pelo `PASSWORD_RESET_TIMEOUT` e remove o token
da URL antes de exibir o formulário de nova senha. A alteração gera auditoria
sem registrar a senha ou o token.

Se for habilitado envio real em outro ambiente, configure `EMAIL_BACKEND`,
`DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` e `EMAIL_USE_SSL` pelas variáveis de
ambiente. As credenciais ficam fora do código.

## Testes

```powershell
.venv/Scripts/python.exe manage.py test apps.accounts --noinput
.venv/Scripts/python.exe manage.py test apps.core.tests_frontend.ShellTestes --debug-mode --noinput
npx playwright test tests/e2e/accounts.spec.ts
```

Os testes do Django cobrem cadastro, login, permissões, CSRF, duplicidade,
envio simulado e o ciclo completo de redefinição. Os testes de navegador
cobrem navegação, validação, visibilidade da senha, carregamento do novo logo,
acessibilidade e ausência de corte horizontal em 320, 390 e 1280 pixels.
