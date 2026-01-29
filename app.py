import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Simulador de Arquitetura AWS", layout="wide")

st.title("Simulador AWS & DBs (sa-east-1)")
st.markdown("""
Esta ferramenta simula custos e viabilidade técnica baseada nos relatórios de engenharia da pasta `docs`.
""")

# --- SIDEBAR: PARÂMETROS DE ENTRADA ---
st.sidebar.header("Parâmetros da Carga de Trabalho")

tps_avg = st.sidebar.number_input("TPS Médio (Transações/seg)", min_value=1, value=300, step=50)
tps_peak = st.sidebar.number_input("TPS de Pico (Black Friday)", min_value=1, value=5000, step=500)
write_ratio = st.sidebar.slider("Proporção de Escrita (%)", 0, 100, 20, help="20% Escrita / 80% Leitura é comum em bancos.")
storage_gb = st.sidebar.number_input("Armazenamento Total (GB)", min_value=1, value=500)
item_size_kb = st.sidebar.number_input("Tamanho Médio do Item (KB)", min_value=1, value=4, help="Tamanho da linha ou documento JSON")

st.sidebar.markdown("---")
st.sidebar.header("Configurações de Arquitetura")
use_strong_consistency = st.sidebar.checkbox("Exigir Consistência Forte (DynamoDB)", value=True, help="Dobra o custo de leitura no DynamoDB.")
use_sharding = st.sidebar.checkbox("Aplicar Write Sharding (Lógica de App)", value=False, help="Necessário para >1000 TPS em conta única.")

# --- MOTOR DE CÁLCULO (PREÇOS ESTIMADOS SA-EAST-1) ---
# Nota: Preços aproximados para fins de estudo (Jan 2026 context)

DAYS_MONTH = 30.5
SECONDS_MONTH = DAYS_MONTH * 24 * 60 * 60

# Cálculo de Requisições Mensais
total_requests_mo = tps_avg * SECONDS_MONTH
write_requests_mo = total_requests_mo * (write_ratio / 100)
read_requests_mo = total_requests_mo * ((100 - write_ratio) / 100)

# 1. CUSTO AURORA POSTGRESQL (db.r7g.2xlarge - Graviton como referência)
# Referência: Docs mencionam r7g para economia
aurora_instance_hourly = 1.20  # Estimativa r7g.2xlarge sa-east-1
aurora_storage_gb_mo = 0.12
aurora_io_rate_million = 0.22  # Custo por milhão de I/Os (Standard)

# Aurora Standard
cost_aurora_std_compute = aurora_instance_hourly * 24 * DAYS_MONTH
cost_aurora_std_storage = storage_gb * aurora_storage_gb_mo
# Estimativa: 1 transação = 2 I/Os (1 índice + 1 tabela) no mínimo
aurora_ios_mo = (write_requests_mo * 2) + (read_requests_mo * 1) 
cost_aurora_std_io = (aurora_ios_mo / 1_000_000) * aurora_io_rate_million
total_aurora_std = cost_aurora_std_compute + cost_aurora_std_storage + cost_aurora_std_io

# Aurora I/O Optimized (Custo Storage maior, IO zero, Instância +30%)
cost_aurora_opt_compute = cost_aurora_std_compute * 1.35
cost_aurora_opt_storage = storage_gb * 0.25 # Storage é mais caro no I/O Optimized
total_aurora_opt = cost_aurora_opt_compute + cost_aurora_opt_storage

# 2. CUSTO DYNAMODB (On-Demand para simplificar simulação de picos)
ddb_write_million = 1.50 # Preço escrita sa-east-1
ddb_read_million = 0.30  # Preço leitura sa-east-1
ddb_storage_gb_mo = 0.28

# Ajuste por tamanho do item (blocos de 1KB no DDB vs 4KB standard)
wcu_multiplier = item_size_kb # 1 WCU por KB
rcu_multiplier = item_size_kb # 1 RCU por 4KB (simplificado para 1 por KB para consistencia forte)

if use_strong_consistency:
    # Strong consistency consome o dobro ou 1 RCU inteira
    rcu_multiplier = item_size_kb 
else:
    rcu_multiplier = item_size_kb / 2

cost_ddb_write = (write_requests_mo * wcu_multiplier / 1_000_000) * ddb_write_million
cost_ddb_read = (read_requests_mo * rcu_multiplier / 1_000_000) * ddb_read_million
cost_ddb_storage = storage_gb * ddb_storage_gb_mo
total_ddb = cost_ddb_write + cost_ddb_read + cost_ddb_storage

# --- DASHBOARD ---

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Requisições/Mês", f"{total_requests_mo/1_000_000:.1f} M")
with col2:
    st.metric("Pico de Escrita", f"{tps_peak * (write_ratio/100):.0f} TPS")
with col3:
    st.metric("Região", "sa-east-1 (São Paulo)")

st.markdown("---")

# --- COMPARAÇÃO DE CUSTOS (AWS) ---
st.markdown("---")
st.subheader("Estimativa de Custo Mensal (USD)")
st.markdown("A análise de custo é focada nos serviços AWS, onde a precificação é mais facilmente modelada.")

cost_data = pd.DataFrame({
    'Serviço': ['Aurora Standard', 'Aurora I/O Optimized', 'DynamoDB (On-Demand)'],
    'Custo Total ($)': [total_aurora_std, total_aurora_opt, total_ddb],
    'Detalhe Principal': [
        f"Custo de I/O: ${cost_aurora_std_io:.2f}", 
        f"Custo de Storage: ${cost_aurora_opt_storage:.2f}", 
        f"Custo de Escrita: ${cost_ddb_write:.2f}"
    ]
})
st.table(cost_data.style.format({'Custo Total ($)': '${:,.2f}'}))


# --- ANÁLISE ARQUITETURAL AVANÇADA ---
st.markdown("---")
st.subheader("Análise Arquitetural Estratégica")
st.markdown("Esta seção compara os bancos de dados sob a ótica de sistemas distribuídos, focando em seus trade-offs fundamentais.")

peak_write_tps = tps_peak * (write_ratio/100)

# --- Aurora Expander ---
with st.expander("Amazon Aurora (PostgreSQL)"):
    st.markdown("##### Análise Dinâmica para sua Carga")
    if peak_write_tps > 1000:
        st.error(f"**Gargalo Crítico:** Com o pico de **{peak_write_tps:.0f} TPS** de escrita, o Aurora sofrerá com 'Row Lock Contention' (disputa de bloqueio na mesma linha), resultando em performance degradada e timeouts.")
    elif peak_write_tps > 300:
        st.warning(f"**Ponto de Atenção:** Com **{peak_write_tps:.0f} TPS** de escrita, será necessário tuning de `fillfactor < 100` e o uso de instâncias potentes para garantir a performance.")
    else:
        st.success(f"**Viável:** A carga de **{peak_write_tps:.0f} TPS** de escrita é suportada tranquilamente por uma instância Aurora padrão, sem necessidade de estratégias complexas.")

    st.markdown("---")
    st.markdown("""
    - **Modelo Principal:** Relacional (SQL) com armazenamento distribuído.
    - **Análise PACELC:** `PC/EC` (Prefere Consistência a Disponibilidade em partição; Prefere Consistência a Latência em operação normal).
    - **Bônus (Prós):** Consistência forte (ACID), flexibilidade de consulta (SQL), ecossistema maduro.
    - **Ônus (Contras):** Escalabilidade de escrita vertical, gargalo de "Hot Row", custo de I/O no modo standard.
    - **Estrutura de Pesquisa:** B-Tree, otimizada para leituras.
    """)
    st.markdown("---")
    st.markdown("##### Complexidade e Ecossistema (Java/Kafka)")
    st.markdown("""
    - **Curva de Aprendizado:** Baixa. Um time Java com experiência em JPA/Hibernate (Spring Data JPA) será produtivo imediatamente. O comportamento é o de um PostgreSQL padrão.
    - **Potenciais Problemas:** *Connection Pool Exhaustion* é um risco real se as transações forem longas ou se o *pool* (ex: HikariCP) não for bem configurado. O tratamento de *failover* do nó de escrita precisa ser gerenciado pela aplicação ou por um driver inteligente.
    - **Integração com Kafka (MSK):** A melhor estratégia para garantir a atomicidade entre a escrita no banco e a publicação de um evento no Kafka é o padrão **Transactional Outbox**. Uma ferramenta como o [Debezium](https://debezium.io/) pode monitorar a tabela de *outbox* via CDC (Change Data Capture) e publicar os eventos, garantindo que nada se perca.
    """)
    st.markdown("---")
    st.markdown("##### Casos de Uso de Tabela Sugeridos")
    st.markdown("""
    - **Ledger de Eventos:** **Perfeito.** Uma tabela de transações imutável é o caso de uso ideal.
    - **Tabela de Saldos:** **Bom, com ressalvas.** Funciona bem até o ponto em que uma única conta (linha) se torna um "hot spot", causando o gargalo de escrita.
    - **Configuração de Cliente:** **Perfeito.** Ideal para dados relacionais, como informações de clientes, permissões e configurações que não mudam com altíssima frequência.
    - **Tabela de Idempotência:** **Perfeito.** A implementação é trivial com uma constraint `UNIQUE` na chave de idempotência, fazendo o banco garantir a prevenção de duplicatas.
    """)
    st.markdown("---")
    st.markdown("##### Principais Configurações")
    st.markdown("""
    - **Instance Class:** (ex: `db.r7g.2xlarge`) Define o poder de CPU e memória. A escolha é diretamente ligada ao TPS que a instância consegue suportar.
    - **Storage Type:** A escolha entre `aurora` (Standard) e `aurora-io-optimized`. Para cargas com mais de 25% de I/O em relação ao custo, o I/O-Optimized geralmente se torna mais barato.
    - **Engine Version:** (ex: `15.3`) Versão do PostgreSQL a ser utilizada.
    """)

# --- DynamoDB Expander ---
with st.expander("Amazon DynamoDB"):
    st.markdown("##### Análise Dinâmica para sua Carga")
    if peak_write_tps > 1000 and not use_sharding:
        st.error(f"**Gargalo Crítico:** Com **{peak_write_tps:.0f} TPS** de escrita e sem 'Write Sharding', sua aplicação sofrerá 'Throttling' severo devido ao limite de 1000 WCU por partição.")
    elif use_sharding:
        st.success(f"**Viável com Sharding:** A estratégia de 'Write Sharding' distribui a carga de **{peak_write_tps:.0f} TPS**, permitindo que o DynamoDB escale horizontalmente sem gargalos.")
    else:
        st.success(f"**Viável:** A carga de **{peak_write_tps:.0f} TPS** é suportada, pois está dentro do limite de uma única partição.")

    st.markdown("---")
    st.markdown("""
    - **Modelo Principal:** NoSQL Chave-Valor e Documento.
    - **Análise PACELC:** `PA/EL` (Prefere Disponibilidade a Consistência em partição; Prefere Latência a Consistência em operação normal).
    - **Bônus (Prós):** Escalabilidade de escrita "infinita" (com sharding), latência previsível, modelo serverless.
    - **Ônus (Contras):** Complexidade de modelagem de dados (NoSQL), transações limitadas, menor flexibilidade de consulta.
    - **Estrutura de Pesquisa:** Hashing na chave de partição.
    """)
    st.markdown("---")
    st.markdown("##### Complexidade e Ecossistema (Java/Kafka)")
    st.markdown("""
    - **Curva de Aprendizado:** Alta. Exige uma mudança de mentalidade, abandonando o modelo relacional. O AWS SDK for Java 2 é poderoso, mas a modelagem de dados e o controle de custos são complexos.
    - **Potenciais Problemas:** Escolher uma chave de partição ruim pode ser desastroso para a performance. O custo pode escalar rapidamente se as leituras consistentes ou transações forem usadas em excesso.
    - **Integração com Kafka (MSK):** **Padrão nativo e poderoso.** Ativar o **DynamoDB Streams** (um feed de CDC) em uma tabela e conectá-lo a uma função Lambda é uma forma serverless e robusta de publicar eventos no Kafka, garantindo a ordem das alterações por partição.
    """)
    st.markdown("---")
    st.markdown("##### Casos de Uso de Tabela Sugeridos")
    st.markdown("""
    - **Ledger de Eventos:** **Bom.** Pode ser modelado usando `conta_id` como Chave de Partição e um `timestamp_transacao_id` como Chave de Ordenação para manter as transações ordenadas por conta.
    - **Tabela de Saldos:** **Ideal para 'Hot Balances'.** É o melhor caso de uso, aplicando-se 'Write Sharding' na `conta_id` para distribuir a carga de escrita.
    - **Configuração de Cliente:** **Bom.** Um cliente e suas configurações podem ser um único item (documento JSON), permitindo leitura/escrita rápida.
    - **Tabela de Idempotência:** **Perfeito.** Usar uma `ConditionExpression` com `attribute_not_exists()` na chave de idempotência é a forma nativa de garantir escritas únicas.
    """)
    st.markdown("---")
    st.markdown("##### Principais Configurações")
    st.markdown("""
    - **Billing Mode:** `PAY_PER_REQUEST` (On-Demand) ou `PROVISIONED`. On-Demand é ideal para cargas imprevisíveis; Provisionado é mais barato para cargas constantes.
    - **Partition Key:** A escolha do atributo para a chave de partição é a decisão mais crítica. Ela deve ter alta cardinalidade para distribuir os dados uniformemente.
    - **RCU/WCU (Read/Write Capacity Units):** No modo `PROVISIONED`, define quantas leituras/escritas por segundo você está pagando.
    - **Global Tables:** Para replicação multi-regional e multi-ativa.
    """)
    
# --- CockroachDB Expander ---
with st.expander("CockroachDB"):
    st.markdown("##### Análise Dinâmica para sua Carga")
    st.success(f"**Nativamente Escalável:** CockroachDB é projetado para escalar escritas horizontalmente. Ele distribui os dados em 'ranges' pelo cluster, evitando o problema de 'Hot Row' que afeta o Aurora em picos de **{peak_write_tps:.0f} TPS**.")
    
    st.markdown("---")
    st.markdown("""
    - **Modelo Principal:** Relacional Distribuído (NewSQL), compatível com a API do PostgreSQL.
    - **Análise PACELC:** `PC/EL` (Prefere Consistência em ambos os cenários, partição e normal).
    - **Bônus (Prós):** Escalabilidade horizontal com SQL e ACID, alta resiliência.
    - **Ônus (Contras):** Maior latência de escrita (consenso Raft), complexidade operacional de um cluster distribuído.
    - **Estrutura de Pesquisa:** Árvore de Merkle sobre um armazenamento chave-valor (Pebble).
    """)
    st.markdown("---")
    st.markdown("##### Complexidade e Ecossistema (Java/Kafka)")
    st.markdown("""
    - **Curva de Aprendizado:** Média. A sintaxe SQL é familiar (compatível com PostgreSQL), mas entender o isolamento `SERIALIZABLE`, o tratamento de *retries* de transação e a topologia do cluster é uma curva de aprendizado real.
    - **Potenciais Problemas:** A latência de escrita é maior que em bancos de nó único devido ao protocolo de consenso (Raft). O time precisa codificar explicitamente o tratamento de *retries* para transações que falham por contenção.
    - **Integração com Kafka (MSK):** **Excelente.** Possui um mecanismo de CDC nativo chamado **Changefeeds**, que pode ser configurado para enviar todas as alterações de uma tabela diretamente para um tópico Kafka em formato Avro ou JSON, com baixa latência.
    """)
    st.markdown("---")
    st.markdown("##### Casos de Uso de Tabela Sugeridos")
    st.markdown("""
    - **Ledger de Eventos:** **Perfeito.** Similar ao Aurora, mas com a vantagem da escalabilidade horizontal nativa.
    - **Tabela de Saldos:** **Excelente.** Lida com "Hot Rows" de forma muito mais elegante que o Aurora devido ao `range splitting` automático, tornando-o um forte candidato para a tabela principal de saldos.
    - **Configuração de Cliente:** **Perfeito.**
    - **Tabela de Idempotência:** **Perfeito.** Usa uma constraint `UNIQUE` padrão do SQL.
    """)
    st.markdown("---")
    st.markdown("##### Principais Configurações")
    st.markdown("""
    - **Número de Nós:** Define a capacidade total e a resiliência do cluster. Aumentar os nós escala tanto o armazenamento quanto o poder de processamento.
    - **Região/Localidade:** Configurações que definem onde os nós estão geograficamente localizados, crucial para baixa latência e sobrevivência a desastres regionais.
    - **Replication Factor:** (ex: 3 ou 5) Quantas cópias de cada 'range' de dados são mantidas no cluster para garantir a resiliência.
    """)

# --- Cassandra/ScyllaDB Expander ---
with st.expander("Apache Cassandra / ScyllaDB"):
    st.markdown("##### Análise Dinâmica para sua Carga")
    st.success(f"**Performance Extrema de Escrita:** Com uma arquitetura otimizada para escritas, estes bancos de dados são projetados para absorver cargas de **{peak_write_tps:.0f} TPS** ou mais, desde que a chave de partição seja bem distribuída.")

    st.markdown("---")
    st.markdown("""
    - **Modelo Principal:** NoSQL Colunar (Wide-Column).
    - **Análise PACELC:** `PA/EL` (Prefere Disponibilidade a Consistência em partição; Prefere Latência a Consistência em operação normal).
    - **Bônus (Prós):** Performance de escrita massiva, escalabilidade linear, alta disponibilidade.
    - **Ônus (Contras):** Consistência eventual como padrão, falta de transações ACID complexas.
    - **Estrutura de Pesquisa:** Log-Structured Merge-Tree (LSM-Tree), otimizada para escritas rápidas.
    """)
    st.markdown("---")
    st.markdown("##### Complexidade e Ecossistema (Java/Kafka)")
    st.markdown("""
    - **Curva de Aprendizado:** Muito Alta. O modelo de dados colunar, a consistência tunável, as estratégias de compactação e o gerenciamento de 'tombstones' são tópicos complexos. O driver Java da DataStax é excelente, mas exige configuração cuidadosa.
    - **Potenciais Problemas:** Performance de leitura pode degradar severamente devido a 'tombstones' ou má modelagem. Garantir consistência forte (`QUORUM` ou `ALL`) impacta a latência e a disponibilidade.
    - **Integração com Kafka (MSK):** Geralmente requer uma implementação do padrão **Transactional Outbox**, similar ao Aurora. Algumas ferramentas de CDC de terceiros existem, mas a integração não é tão nativa quanto em outros bancos.
    """)
    st.markdown("---")
    st.markdown("##### Casos de Uso de Tabela Sugeridos")
    st.markdown("""
    - **Ledger de Eventos:** **Excelente.** É o caso de uso ideal, otimizado para ingestão em altíssima velocidade de dados imutáveis (séries temporais).
    - **Tabela de Saldos:** **Não Recomendado.** A falta de transações ACID torna a atualização de saldos (leitura + escrita) arriscada e complexa, exigindo bloqueios distribuídos (ex: com Zookeeper) que anulam os benefícios de performance do banco.
    - **Configuração de Cliente:** **Usável.** Funciona, mas a rigidez das consultas pode ser um problema a longo prazo.
    - **Tabela de Idempotência:** **Usável, com ressalvas.** É possível com Lightweight Transactions (LWT) e `IF NOT EXISTS`, mas esta operação é significativamente mais lenta pois exige um consenso (Paxos).
    """)
    st.markdown("---")
    st.markdown("##### Principais Configurações")
    st.markdown("""
    - **Replication Factor:** (ex: 3) Define em quantos nós cada pedaço de dado é replicado. Essencial para a disponibilidade.
    - **Consistency Level:** (ex: `ONE`, `QUORUM`, `ALL`) Configurado por operação na aplicação. Define o trade-off entre consistência e latência para cada leitura/escrita.
    - **Compaction Strategy:** (ex: `SizeTiered`, `Leveled`) Define como os dados são organizados e mesclados em disco, com grande impacto na performance de leitura.
    """)

# --- SÍNTESE ESTRATÉGICA ---
st.markdown("---")
st.subheader("Síntese Estratégica")

st.markdown("""
A ferramenta não visa eleger um "vencedor", mas sim iluminar os **trade-offs** fundamentais de cada arquitetura. A escolha correta depende do principal "driver" de negócio e da cultura de engenharia da sua equipe.

- Se a **prioridade máxima é a integridade dos dados, a conformidade com ACID e a flexibilidade para análises complexas**, a familiaridade do SQL aponta para **Aurora** ou **CockroachDB**. Aurora é mais simples para começar; CockroachDB é arquitetado para escala global desde o início.

- Se a **escala de escrita massiva e a disponibilidade total são inegociáveis**, e sua equipe está preparada para uma mudança de paradigma, o ecossistema NoSQL é o caminho. **DynamoDB** oferece a maior simplicidade operacional (serverless). **ScyllaDB/Cassandra** oferecem a performance de escrita mais "crua" e controle sobre a infraestrutura.

- **Para um sistema de ledger financeiro**, uma abordagem híbrida é frequentemente a ideal: usar um banco de dados relacional distribuído (Aurora/CockroachDB) para o "livro-razão" e saldos, enquanto um banco NoSQL (DynamoDB/Scylla) pode ser usado para absorver picos de eventos ou dados de sessão.

Use a análise acima para pesar o bônus e o ônus de cada sistema contra os seus requisitos específicos e a capacidade técnica do seu time.
""")


