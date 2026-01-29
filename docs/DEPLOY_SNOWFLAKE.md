# Deploy do Aplicativo Streamlit no Snowflake (Privado)

Este guia detalha o processo para publicar seu aplicativo Streamlit diretamente no Snowflake, garantindo que ele permaneça privado e acessível apenas para os usuários que você definir. O processo utiliza a interface web do Snowflake, chamada **Snowsight**.

**Pré-requisitos:**
1.  **Conta no Snowflake:** Você precisa de acesso a uma conta Snowflake.
2.  **Permissões:** Seu usuário precisa de um `ROLE` (papel) com permissões para criar `DATABASE`, `SCHEMA`, `STAGE` e `STREAMLIT`. Geralmente, o papel `ACCOUNTADMIN` tem essas permissões.
3.  **Arquivos do Projeto:** Tenha os arquivos `app.py` e `requirements.txt` em seu computador.

---

### Passo 1: Criar um Banco de Dados e um Schema

Todos os objetos no Snowflake, incluindo seu aplicativo, precisam estar organizados dentro de um banco de dados e um schema.

1.  Faça login no **Snowsight**.
2.  No menu à esquerda, clique em **"Data"** -> **"Databases"**.
3.  Clique no botão **"+ Database"**.
    *   **Nome do Banco de Dados:** `STREAMLIT_APPS`
    *   Clique em **"Create"**.
4.  O Snowflake cria automaticamente um schema chamado `PUBLIC` dentro do novo banco de dados. Vamos usá-lo.

---

### Passo 2: Criar um "Stage" para os Arquivos do App

Um "Stage" é um local de armazenamento no Snowflake onde você fará o upload dos arquivos do seu projeto.

1.  No menu à esquerda, navegue para o schema que você acabou de criar: **"Data"** -> **"Databases"** -> **STREAMLIT_APPS** -> **PUBLIC**.
2.  Com o schema `PUBLIC` selecionado, clique em **"Create"** -> **"Stage"**.
3.  Selecione **"Standard"**.
4.  Preencha os detalhes:
    *   **Stage Name:** `CALCULATOR_AWS_STAGE`
    *   **Directory enabled:** Marque esta opção.
    *   O resto pode ser deixado como padrão.
5.  Clique em **"Create"**.

---

### Passo 3: Fazer Upload dos Arquivos do Projeto

Agora, vamos colocar o código do seu aplicativo no Stage que acabamos de criar.

1.  Ainda na mesma tela, clique no stage `CALCULATOR_AWS_STAGE` que você criou.
2.  Você verá que o stage está vazio. Clique no botão **"+ Files"** no canto superior direito.
3.  Selecione **"Upload files"**.
4.  Faça o upload de **`app.py`** e **`requirements.txt`** do seu computador para o stage.
    *   **Importante:** Verifique se os arquivos foram carregados para a pasta raiz (`/`) do stage.

---

### Passo 4: Criar o Aplicativo Streamlit

Com os arquivos no lugar, agora você pode criar o aplicativo.

1.  No menu principal à esquerda, clique em **"Streamlit"**.
2.  Clique no botão **"+ Streamlit App"**.
3.  Preencha o formulário de criação:
    *   **Name:** `Calculadora_Custos_AWS`
    *   **App location:** Selecione o schema onde você criou o stage: `STREAMLIT_APPS.PUBLIC`.
    *   **App file:** aponte para o arquivo principal no seu stage: `@STREAMLIT_APPS.PUBLIC.CALCULATOR_AWS_STAGE/app.py`.
    *   **Warehouse:** Selecione um [Warehouse](https://docs.snowflake.com/en/user-guide/warehouses-overview) para executar o aplicativo. Pode ser o `COMPUTE_WH` padrão ou outro que você tenha. O warehouse é a "potência de computação" que executa o app.
4.  Clique em **"Create"**.

O Snowflake levará um ou dois minutos para instalar as dependências do seu `requirements.txt` e iniciar o aplicativo pela primeira vez.

---

### Passo 5: Gerenciar Acesso (Torná-lo Privado)

Por padrão, apenas o criador (a sua `ROLE`) pode ver o aplicativo. Para compartilhar com outras pessoas ou equipes (outras `ROLEs`) dentro da sua organização Snowflake:

1.  Clique no seu aplicativo recém-criado na lista de Streamlit Apps.
2.  No canto superior direito, clique em **"Share"**.
3.  Procure pelas `ROLEs` (papéis) com as quais você deseja compartilhar e conceda a eles o privilégio de **"Usage"**.

Somente as `ROLEs` com essa permissão poderão ver e acessar o aplicativo. Para todos os outros, ele não existirá.

---

### Como Rodar o App no Celular?

Depois de publicado, seu aplicativo tem uma URL única dentro do ambiente Snowflake.

1.  Abra o aplicativo na interface do Snowsight.
2.  Copie a URL do navegador.
3.  Envie essa URL para si mesmo e abra no navegador do seu celular.
4.  **Importante:** Você precisará fazer login na sua conta Snowflake no navegador do celular para acessar o aplicativo, pois ele é privado e seguro.

Seguindo esses passos, seu aplicativo estará funcionando de forma segura e privada dentro do seu ecossistema Snowflake, e você poderá demonstrá-lo em qualquer dispositivo com um navegador.