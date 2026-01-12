# Guia: Enviando o Projeto para o GitHub via Terminal

Este guia mostra um passo a passo de como enviar este projeto para um **repositório privado** no GitHub usando a linha de comando.

### Pré-requisitos

1.  **Git Instalado:** Você precisa ter o Git instalado na sua máquina. Se não tiver, baixe em [git-scm.com](https://git-scm.com/).
2.  **Conta no GitHub:** Você precisa de uma conta no [github.com](https://github.com).
3.  **Autenticação na Linha de Comando:** Você precisa estar autenticado para enviar alterações para o GitHub. A forma mais segura e recomendada é usando **SSH keys** ou um **Personal Access Token (PAT)**. Siga o guia oficial do GitHub para configurar a autenticação:
    - [Autenticando com SSH](https://docs.github.com/pt/authentication/connecting-to-github-with-ssh)
    - [Criando um Personal Access Token](https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

---

### Passo 1: Iniciar o Repositório Git Local

Se você ainda não iniciou um repositório Git neste projeto, o primeiro passo é fazê-lo.

1.  Abra seu terminal na pasta raiz do projeto (`calculator_aws_DBs_tradeoff_cost`).

2.  Execute o comando `git init` para criar um novo repositório Git. É comum usar `main` como o nome da branch principal.
    ```bash
    git init -b main
    ```

---

### Passo 2: Adicionar e "Comitar" os Arquivos

Agora vamos adicionar todos os arquivos do projeto ao controle de versão e criar nosso primeiro "commit" (um snapshot dos arquivos).

1.  Adicione todos os arquivos ao "staging area" do Git. O ponto (`.`) significa "todos os arquivos e pastas a partir do diretório atual".
    ```bash
    git add .
    ```

2.  Crie o commit com uma mensagem descritiva.
    ```bash
    git commit -m "Commit inicial do projeto de simulação de arquitetura de DB"
    ```

---

### Passo 3: Criar o Repositório Remoto no GitHub

Agora vamos para o site do GitHub para criar o repositório que receberá nossos arquivos.

1.  Faça login na sua conta do GitHub.
2.  No canto superior direito, clique no ícone de `+` e selecione **"New repository"**.
3.  **Repository name:** Dê um nome ao seu repositório (ex: `simulador-db-strategy`).
4.  **Description (Opcional):** Adicione uma breve descrição.
5.  **IMPORTANTE:** Selecione a opção **"Private"** para garantir que apenas você (e quem você convidar) possa ver o código.
6.  **NÃO** marque nenhuma das opções "Initialize this repository with" (como `README`, `.gitignore` ou `license`), pois já temos nosso projeto localmente.
7.  Clique em **"Create repository"**.

---

### Passo 4: Conectar o Repositório Local ao Remoto e Enviar

Após criar o repositório, o GitHub mostrará uma página com alguns comandos. Vamos usar os comandos da seção "...or push an existing repository from the command line".

1.  Copie a linha que começa com `git remote add origin`. Ela conectará seu repositório local ao repositório remoto que você acabou de criar. O formato será algo como:
    ```bash
    git remote add origin git@github.com:SEU_USUARIO/SEU_REPOSITORIO.git
    ```
    *Nota: A URL pode ser `https` ou `git@` (SSH). Ambas funcionam se você estiver autenticado corretamente.*

2.  Execute o comando que você copiou no seu terminal.

3.  Agora, envie (push) seu commit da branch `main` local para a branch `main` no repositório remoto (`origin`). A flag `-u` configura o "upstream" para que, no futuro, você possa apenas usar `git push`.
    ```bash
    git push -u origin main
    ```

---

**Pronto!** Se você atualizar a página do seu repositório no GitHub, verá todos os arquivos do projeto lá. A partir de agora, para salvar novas alterações, o fluxo será:

```bash
# 1. Adicionar as novas alterações
git add .

# 2. "Comitar" as alterações
git commit -m "Mensagem descrevendo a nova alteração"

# 3. Enviar para o GitHub
git push
```
