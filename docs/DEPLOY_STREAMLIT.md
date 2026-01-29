# Guia: Deploy da Aplicação na Streamlit Community Cloud

A Streamlit Community Cloud é uma plataforma gratuita que permite implantar e compartilhar suas aplicações Streamlit publicamente. Este guia mostra como fazer isso.

### Pré-requisitos

1.  **Projeto no GitHub:** Sua aplicação **precisa** estar em um repositório no GitHub. Siga o guia [`DEPLOY_GITHUB.md`](./DEPLOY_GITHUB.md) se ainda não o fez. Para a Streamlit Community Cloud, o repositório pode ser público ou privado.

2.  **Arquivo `requirements.txt`:** A plataforma precisa saber quais bibliotecas Python instalar. O arquivo `requirements.txt` na raiz do projeto serve para isso. Este projeto já possui o arquivo necessário com o seguinte conteúdo:
    ```
    streamlit
    pandas
    matplotlib
    numpy
    ```

3.  **Conta na Streamlit Community Cloud:** Você precisará se inscrever (é gratuito) em [share.streamlit.io](https://share.streamlit.io/). A forma mais fácil é se inscrever usando sua conta do GitHub.

---

### Passo 1: Conectar sua Conta do GitHub

Se você se inscreveu usando sua conta do GitHub, a conexão já deve estar estabelecida. Caso contrário, nas configurações da sua conta na Streamlit Community Cloud, autorize o acesso aos seus repositórios do GitHub.

---

### Passo 2: Criar uma Nova Aplicação (Deploy)

1.  Acesse seu workspace na Streamlit Community Cloud: [share.streamlit.io](https://share.streamlit.io/).

2.  No canto superior direito, clique no botão **"New app"**.

3.  Você verá uma tela para configurar sua aplicação. Preencha os campos:
    - **Repository:** Escolha o repositório do GitHub onde você enviou o projeto (ex: `seu_usuario/simulador-db-strategy`). Se for um repositório privado, você poderá vê-lo na lista.
    - **Branch:** Digite o nome da sua branch principal (geralmente `main` ou `master`).
    - **Main file path:** Este é o caminho para o seu arquivo Python principal. Para este projeto, digite `app.py`.

4.  Abaixo dos campos principais, há um link **"Advanced settings..."**. Você pode usá-lo para:
    - **Python version:** Escolher uma versão específica do Python se seu projeto exigir. Geralmente, o padrão funciona bem.
    - **Secrets:** Se sua aplicação precisasse de chaves de API ou senhas, você as adicionaria aqui de forma segura, em vez de colocá-las no código. Para este projeto, não é necessário.

5.  Clique no botão **"Deploy!"**.

---

### Passo 3: Acompanhar a Implantação

Após clicar em "Deploy!", você será levado para a página da sua aplicação.

- A primeira implantação pode levar alguns minutos. Você verá logs em tempo real mostrando o Streamlit instalando as dependências do seu `requirements.txt`. É comum ver o log de instalação do `pip`.
- Se tudo correr bem, os logs terminarão e sua aplicação aparecerá na tela, pronta para ser usada e compartilhada.
- Se houver um erro (ex: uma biblioteca faltando no `requirements.txt`), a aplicação mostrará uma mensagem de erro, e você pode usar os logs para depurar.

---

**Pronto!** Sua aplicação agora está online e acessível através da URL fornecida pela Streamlit (ex: `https://seu-nome-de-usuario-simulador-db-strategy-app-xyz.streamlit.app`).

### Atualizando a Aplicação

A melhor parte da integração com o GitHub é a atualização automática. Sempre que você enviar novas alterações (`git push`) para a branch que você implantou (`main`), a Streamlit Community Cloud detectará a mudança e reimplantará sua aplicação automaticamente com o código mais recente.
