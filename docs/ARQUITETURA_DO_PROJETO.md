# Arquitetura do Projeto - Simulador de Custos AWS

Este documento descreve a arquitetura técnica do "Simulador de Trade-offs", explicando como seus componentes interagem para transformar dados de entrada em análises de custo e viabilidade.

## Visão Geral

O projeto tem como objetivo principal traduzir conhecimento teórico sobre performance e custo de bancos de dados AWS em uma ferramenta de simulação prática. Ele é construído como uma aplicação monolítica simples usando Python e a biblioteca Streamlit, o que permite que a lógica de backend e a interface de usuário residam no mesmo arquivo (`app.py`).

## Componentes Principais

### 1. `app.py` (Interface e Lógica Principal)

Este é o coração da aplicação. Ele pode ser dividido em três áreas de responsabilidade:

- **Interface de Usuário (Frontend):** Construído inteiramente com componentes do Streamlit (`st.sidebar`, `st.number_input`, `st.slider`, etc.). O layout é organizado para coletar os parâmetros da carga de trabalho na barra lateral e exibir os resultados no painel principal.
- **Motor de Cálculo (Backend):** Uma série de cálculos em Python puro que estimam os custos mensais.
    - **Preços:** Os custos unitários (ex: `aurora_instance_hourly`, `ddb_write_million`) são valores fixos (hardcoded) no código, representando uma estimativa para a região `sa-east-1` em um determinado momento. Para um projeto em produção, esses valores poderiam ser consumidos de uma API de precificação da AWS.
    - **Lógica de Custo:**
        - **Aurora:** Calcula o custo de computação (instância/hora), armazenamento (GB/mês) e, para o modo Standard, o custo de I/O com base no número total de leituras e escritas.
        - **DynamoDB:** Calcula o custo de escrita e leitura com base no número de requisições e no tamanho do item (que impacta as WCUs/RCUs), além do custo de armazenamento.
- **Motor de Análise de Viabilidade:** Esta é a "inteligência" do simulador. Consiste em uma série de estruturas condicionais (`if/elif/else`) que aplicam as regras extraídas da pasta `/docs`.
    - **Exemplo (Risco de Hot Row):**
        ```python
        peak_write_tps = tps_peak * (write_ratio/100)
        if peak_write_tps > 1000 and not use_sharding:
            st.error("CRÍTICO: Risco de Hot Row Lock!")
        ```
      Esta lógica implementa diretamente a regra de que uma única linha em um banco relacional tem um limite físico de transações concorrentes.

### 2. `/docs` (Base de Conhecimento)

Esta pasta funciona como a fonte da verdade para a lógica de negócio do simulador. Os arquivos Markdown não são lidos pela aplicação em tempo de execução; em vez disso, suas conclusões foram **traduzidas manualmente para a lógica de Python** no `app.py`.

- `Estudo de Trade-offs em Arquitetura de Dados.md`
- `Otimização Financeira e Bancária em TPS.md`
- `Arquitetura Híbrida_ Síncrono vs. Assíncrono.md`

### 3. `docs/INFRA_SETUP.md` (Guia de Provisionamento)

Este documento desacopla a simulação da implementação real. Ele serve como uma "ponte" para o próximo passo de um projeto real, fornecendo exemplos de código **Terraform** que demonstram como provisionar a infraestrutura que foi simulada. Ele também clarifica quais conceitos são configurações de infraestrutura (ex: `storage_type` no Aurora) e quais são padrões de aplicação (ex: `Write Sharding` e `Consistent Read`).

## Fluxo de Dados e Lógica

O fluxo de execução da aplicação é linear e simples, típico de uma aplicação Streamlit:

1.  **Entrada do Usuário:** O usuário ajusta os sliders e campos de número na barra lateral. A cada ajuste, o Streamlit re-executa o script `app.py`.
2.  **Cálculo de Custos:** O script utiliza os valores de entrada para calcular os custos totais para `Aurora Standard`, `Aurora I/O Optimized` e `DynamoDB On-Demand`.
3.  **Análise de Viabilidade:** O script avalia o `tps_peak` e outras configurações para identificar possíveis gargalos de arquitetura, gerando mensagens de sucesso, aviso ou erro.
4.  **Renderização do Output:** O Streamlit renderiza os resultados no painel principal, exibindo as métricas, os gráficos de barras e as conclusões do "agente".

## Possíveis Melhorias

Para evoluir este protótipo, as seguintes melhorias poderiam ser implementadas:

- **Atualização Dinâmica de Preços:** Integrar com a [AWS Price List API](https://aws.amazon.com/blogs/aws/new-aws-price-list-api/) para usar preços em tempo real.
- **Mais Opções de Configuração:** Adicionar mais tipos de instância, opções de provisionamento (ex: DynamoDB Provisioned Throughput) e outras regiões da AWS.
- **Simulação de Custos de Rede:** Incluir uma estimativa para custos de transferência de dados entre zonas de disponibilidade ou para a internet.
- **Testes Unitários:** Adicionar testes para o motor de cálculo para garantir a precisão das estimativas.
