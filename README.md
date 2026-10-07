# Simulador Estratégico de Arquitetura de Bancos de Dados

Este projeto é uma ferramenta interativa de estudo, construída com Python e Streamlit, projetada para analisar e comparar as arquiteturas de bancos de dados modernos para sistemas transacionais de alta vazão (TPS).

O foco da ferramenta evoluiu de uma simples calculadora de custos para um **guia estratégico** que explora os trade-offs fundamentais entre quatro famílias de bancos de dados:

1.  **Amazon Aurora (PostgreSQL)**
2.  **Amazon DynamoDB**
3.  **CockroachDB**
4.  **Apache Cassandra & ScyllaDB**

## A Proposta

A escolha de um banco de dados para um sistema crítico (financeiro, de pagamentos, etc.) é uma das decisões de arquitetura mais impactantes. Esta ferramenta visa auxiliar nessa decisão, não fornecendo uma resposta definitiva, mas sim iluminando os "prós e contras" de cada abordagem sob diversas óticas:

- **Análise de Custo:** Estimativas aproximadas (região sa-east-1, preços de referência de jan/2026, só para estudo) para os serviços gerenciados da AWS (Aurora e DynamoDB).
- **Teoria de Sistemas Distribuídos:** Análise de cada banco sob a ótica dos teoremas CAP e PACELC.
- **Gargalos de Performance:** Simulação dinâmica de como a carga de trabalho (TPS, proporção de escrita) impacta a viabilidade de cada arquitetura, alertando sobre "Hot Spots" e contenção.
- **Complexidade de Ecossistema:** Discussão sobre a curva de aprendizado e os desafios de integração em um ambiente de microsserviços (com foco em Java e Kafka/MSK).
- **Modelagem de Dados:** Sugestões de como modelar tabelas comuns (Ledger, Saldos, Idempotência) em cada banco de dados.

## Como Usar

### Pré-requisitos
- Python 3.8+

### Instalação

1.  Clone este repositório:
    ```bash
    git clone <url_do_repositorio>
    cd calculator_aws_DBs_tradeoff_cost
    ```

2.  Instale as dependências a partir do `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

### Execução

Execute a aplicação Streamlit com o seguinte comando:

```bash
streamlit run app.py
```

A interface do simulador será aberta em seu navegador, onde você poderá ajustar os parâmetros da carga de trabalho e explorar a análise detalhada de cada banco de dados.

## Estrutura da Documentação

A pasta [`/docs`](./docs/) contém a base de conhecimento do projeto e guias de implantação.

### Análise Individual dos Bancos de Dados

Para um mergulho profundo em cada sistema, consulte os seguintes documentos:

- **[Amazon Aurora (PostgreSQL)](./docs/aurora.md)**
- **[Amazon DynamoDB](./docs/dynamodb.md)**
- **[CockroachDB](./docs/cockroachdb.md)**
- **[Apache Cassandra & ScyllaDB](./docs/cassandra_scylladb.md)**

### Guias de Implantação

- **[Deploy no GitHub](./docs/DEPLOY_GITHUB.md)**: Passo a passo para enviar seu projeto para um repositório privado no GitHub.
- **[Deploy na Streamlit Community Cloud](./docs/DEPLOY_STREAMLIT.md)**: Passo a passo para publicar sua aplicação na nuvem da Streamlit.

### Documentos de Referência Adicionais

- **[`INFRA_SETUP.md`](./docs/INFRA_SETUP.md):** Exemplos de código Terraform para provisionar a infraestrutura.
- **[`ARQUITETURA_DO_PROJETO.md`](./docs/ARQUITETURA_DO_PROJETO.md):** Como os componentes do simulador interagem.
- Relatórios de pesquisa que serviram de base para a lógica do simulador (elaborados com apoio de ferramentas de IA e revisados pelo autor):
  [Estudo de Trade-offs em Arquitetura de Dados](<./docs/Estudo de Trade-offs em Arquitetura de Dados.md>),
  [Otimização Financeira e Bancária em TPS](<./docs/Otimização Financeira e Bancária em TPS.md>) e
  [Arquitetura Híbrida: Síncrono vs. Assíncrono](<./docs/Arquitetura Híbrida_ Síncrono vs. Assíncrono.md>).

## Projeto relacionado

[`Simulators_strategy_databases`](https://github.com/o-allanribeiro/Simulators_strategy_databases):
simulações interativas de locking, concorrência otimista, write sharding e netting multilateral para as mesmas cargas de alto TPS.
