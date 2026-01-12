# **Relatório de Engenharia de Sistemas: Arquitetura Híbrida de Alta Frequência para Ambientes Financeiros**

## **1\. Introdução: O Desafio da Escala na Modernização Bancária**

O cenário financeiro contemporâneo, particularmente no contexto brasileiro, atravessa uma transformação estrutural impulsionada pela demanda por pagamentos instantâneos, open finance e a ubiquidade dos canais digitais. Instituições financeiras tradicionais, cujos núcleos transacionais (Core Banking) foram desenhados décadas atrás sob paradigmas de processamento em lote (batch) e baixa concorrência, enfrentam agora o desafio de suportar cargas de trabalho contínuas e de altíssima frequência. A necessidade de processar 5.000 Transações por Segundo (TPS) em uma única conta — um cenário comum para grandes varejistas, gateways de pagamento ou contas concentradoras de liquidação — expõe as limitações físicas e lógicas das arquiteturas monolíticas baseadas em mainframes legados, tipicamente operando sobre IBM DB2.1

Este relatório técnico apresenta uma análise exaustiva e multidisciplinar sobre a engenharia de sistemas híbridos que integram a nuvem (AWS) ao legado on-premise (DB2). O foco central reside na resolução do problema de concorrência em "hot rows" (linhas quentes) de tabelas de saldo, contrastando os modelos de consistência síncrona e assíncrona. Analisaremos profundamente os trade-offs entre diferentes motores de banco de dados — Amazon DynamoDB, Amazon Aurora PostgreSQL, Redis, ScyllaDB e CockroachDB — e proporemos estratégias de convivência baseadas em orquestração de microserviços Java, modelagem de dados segregada (Ledger vs. Saldo) e fluxos compensatórios.

A premissa fundamental desta análise é que a escalabilidade linear para 5.000 TPS em uma única entidade lógica (uma conta) é inviável sob os padrões tradicionais de bloqueio de banco de dados (locking) e consistência ACID estrita síncrona. A solução exige uma mudança de paradigma em direção à consistência eventual segura, particionamento de escrita e desacomplamento temporal entre a autorização do crédito (nuvem) e a liquidação contábil (mainframe).2

## ---

**2\. Fundamentos Teóricos: Panoramas de Integração e Consistência**

A arquitetura de sistemas distribuídos para o setor financeiro é governada por leis físicas de latência e teoremas lógicos de consistência, notadamente o Teorema CAP (Consistência, Disponibilidade e Tolerância a Partição). No contexto de uma arquitetura híbrida AWS \+ DB2, a decisão entre integração síncrona e assíncrona define não apenas a performance, mas a integridade financeira e a resiliência do sistema.

### **2.1 O Panorama Síncrono: A Ilusão da Segurança Absoluta**

O modelo síncrono representa a extensão da transacionalidade do mainframe para a nuvem. Neste cenário, uma operação iniciada em um microserviço Java na AWS (por exemplo, uma solicitação de crédito) mantém uma conexão aberta até que a transação seja efetivada e commitada no DB2 on-premise.

#### **2.1.1 Mecânica e Limitações Físicas**

Em uma transação síncrona clássica, o orquestrador na nuvem bloqueia recursos locais e aguarda a confirmação do sistema de registro (System of Record \- SoR). Se considerarmos uma latência de rede (round-trip time) de 20ms entre a região da AWS (e.g., sa-east-1) e o Data Center do banco, somada ao tempo de processamento do COBOL/DB2 (digamos, 50ms sob carga), o tempo total de resposta (RT) mínimo é de 70ms.

Para atingir 5.000 TPS com um RT de 70ms, a Lei de Little ($L \= \\lambda W$) dita que o sistema deve manter 350 requisições concorrentes ativas simultaneamente ($5000 \\times 0.07$). Embora pareça gerenciável para servidores de aplicação modernos, o gargalo reside no banco de dados. O DB2, ao receber 5.000 atualizações por segundo na *mesma linha* de saldo (a conta concentradora), serializará essas operações para garantir o isolamento ACID.3

O bloqueio de linha (Row Lock) no DB2 impede que duas transações alterem o saldo simultaneamente. Se cada atualização de linha levar 1ms, o throughput máximo teórico para *aquela conta específica* é de 1.000 TPS. Qualquer carga acima disso cria uma fila de espera exponencial. Aos 5.000 TPS, o sistema entra em colapso devido a *Lock Wait Timeouts* e exaustão de threads no pool de conexões do CICS ou DB2 Connect.2

Adicionalmente, o modelo síncrono acopla a disponibilidade da nuvem à do mainframe. Se o DB2 entrar em manutenção ou a conexão Direct Connect falhar, o sistema de pagamentos na nuvem (PIX, cartões) torna-se indisponível, violando requisitos de alta disponibilidade (99.999%) esperados em sistemas críticos.

### **2.2 O Panorama Assíncrono: A Realidade da Alta Frequência**

Para superar as limitações físicas de bloqueio e latência, a arquitetura deve adotar o modelo assíncrono. Neste paradigma, a AWS atua como um sistema de autorização e captura, enquanto o DB2 atua como o sistema de liquidação diferida.

#### **2.2.1 Desacomplamento Temporal**

A transação é dividida em dois momentos distintos:

1. **Autorização (Tempo Real \- AWS):** O microserviço valida se a conta possui fundos ou limite e "reserva" o valor. Esta operação ocorre em um banco de dados na nuvem, otimizado para escrita e baixa latência. O usuário recebe a confirmação de sucesso neste ponto.  
2. **Liquidação (Tempo Diferido \- DB2):** As transações autorizadas são enviadas para o mainframe em segundo plano, via fluxos de eventos (Kafka/Kinesis), muitas vezes agrupadas (micro-batching) para reduzir a pressão de IOPS no DB2.4

#### **2.2.2 Consistência Eventual Segura**

O desafio central do modelo assíncrono é o risco de *Double Spending* (gasto duplo) ou *Divergência de Saldo*. Se a AWS autorizar um débito baseada em um saldo desatualizado (porque uma transação no mainframe ainda não foi replicada para a nuvem), o banco assume um risco financeiro.

Para mitigar isso, utiliza-se o conceito de Saldo Sombra (Shadow Balance) na AWS. Este saldo não é uma réplica exata do DB2, mas uma visão conservadora:

$$\\text{Saldo Disponível (AWS)} \= \\text{Saldo Confirmado (DB2)} \- \\text{Débitos Pendentes (AWS)}$$  
O orquestrador na nuvem deve ser capaz de validar fluxos compensatórios. Se uma transação é autorizada na AWS mas rejeitada no DB2 (por exemplo, devido a um bloqueio judicial inserido diretamente no mainframe), o orquestrador deve receber esse evento de rejeição e executar uma transação de estorno (compensação) no Saldo Sombra, notificando o cliente.6

## ---

**3\. Modelagem de Dados para Engenharia de Alta Vazão**

A modelagem de dados para suportar 5.000 TPS em uma única conta exige o abandono da prática tradicional de manter um único registro de "Saldo Atual" que é atualizado destrutivamente (UPDATE accounts SET balance \= balance \+ x). Em vez disso, adota-se o padrão de **Event Sourcing** ou **Ledger-based architecture**.

### **3.1 Dicotomia: Tabela de Lançamentos (Ledger) vs. Tabela de Saldo**

A separação de responsabilidades entre a gravação do fato financeiro (o débito/crédito) e o cálculo do estado atual (o saldo) é crucial.

#### **3.1.1 Tabela de Lançamentos (Ledger)**

Esta tabela é imutável e "Append-Only" (apenas inserção). Cada transação é um novo registro.

* **Vantagem:** Inserções são muito mais rápidas que atualizações porque não exigem bloqueios de leitura-modificação-gravação. Várias threads podem inserir registros para a mesma conta simultaneamente sem contenção de bloqueio na linha do banco de dados, desde que o banco suporte concorrência de inserção (o que bancos modernos fazem bem).2  
* **Estrutura Típica:** TransactionID, AccountID, Amount, Type (Credit/Debit), Timestamp, Status.

#### **3.1.2 Tabela de Saldo (Snapshot)**

Calcular o saldo somando milhões de lançamentos em tempo real é inviável (latência de leitura alta). Portanto, mantemos uma tabela de saldo que é um "Snapshot" ou "View" materializada.

* **Desafio:** Atualizar esta tabela em tempo real traz de volta o problema da "Hot Row".  
* **Estratégia:** O saldo pode ser *eventualmente consistente* para leituras de consulta, mas o *Saldo Disponível* usado para autorização deve ser estritamente controlado.

### **3.2 Modelagem de Créditos: À Vista vs. Provisionado**

Para o orquestrador validar fluxos, distinguimos dois tipos de saldo lógico:

1. **Crédito à Vista (Saldo Contábil):** Representa o dinheiro que já foi liquidado definitivamente. No modelo híbrido, este valor geralmente vem da sincronização com o DB2 (e.g., via Change Data Capture \- CDC).  
2. **Crédito Provisionado (Bloqueios/Reservas):** Representa transações que ocorreram na nuvem (AWS) mas ainda não foram confirmadas pelo mainframe.

O **Orquestrador de Transações** opera sobre a seguinte lógica de validação:

* Ao receber uma requisição de débito de R$ 100:  
  1. Lê o último *Saldo Contábil* sincronizado (ex: R$ 1.000).  
  2. Soma todos os *Créditos Provisionados* ativos (ex: R$ 50 em débitos pendentes).  
  3. Calcula o *Poder de Compra*: $1000 \- 50 \= 950$.  
  4. Se $950 \\ge 100$, autoriza.  
  5. Cria um novo registro de *Crédito Provisionado* de R$ 100 com TTL (Time-to-Live) para expiração automática caso não haja confirmação de liquidação.7

### **3.3 Estratégias de Sharding para Contas Quentes**

Para sustentar 5.000 TPS de escrita em uma única conta lógica (o ledger), é necessário usar **Write Sharding** (Particionamento de Escrita).8

A conta "Hot Account" (ex: ID 12345\) é subdividida logicamente em $N$ partições físicas.

* **Técnica:** Ao inserir no Ledger, o aplicativo adiciona um sufixo aleatório ao ID da conta: 12345\_01, 12345\_02,..., 12345\_10.  
* **Escrita:** O banco de dados distribui essas chaves em nós/partições diferentes. Com 10 shards, cada um recebe \~500 TPS, o que é gerenciável.  
* **Leitura (Cálculo de Saldo):** Para saber o saldo total, o sistema deve ler os agregados de todos os shards (12345\_\*) e somá-los (Scatter-Gather). Isso aumenta a latência de leitura, mas viabiliza a vazão de escrita.8

## ---

**4\. Análise Profunda de Bancos de Dados e Trade-offs**

A escolha do motor de banco de dados na AWS é determinante para o custo, performance e complexidade operacional. Analisaremos DynamoDB, Aurora, Redis, Scylla e CockroachDB sob a ótica de 5.000 TPS.

### **4.1 Amazon DynamoDB: A Escolha "Serverless"**

O DynamoDB é um banco NoSQL chave-valor altamente escalável, mas com limitações estritas por partição.

* **Arquitetura:** Baseado em particionamento consistente. Cada partição física suporta, por padrão, 1.000 WCU (Unidades de Capacidade de Escrita) e 3.000 RCU.  
* **O Problema de 5.000 TPS:** Uma única conta (PartitionKey=ContaX) reside em uma única partição física. Enviar 5.000 escritas por segundo para essa chave resultará em *Throttling* imediato e rejeição de requisições, pois excede o limite de 1.000 WCU.8  
* **Solução (Write Sharding):** Obrigatório. Usar sufixos aleatórios (ContaX\#1 a ContaX\#10) distribui a carga.  
* **Trade-offs:**  
  * *Prós:* Latência previsível de um dígito de milissegundo; escalabilidade infinita com sharding correto; integração nativa com Lambda e Kinesis; sem manutenção de servidor.  
  * *Contras:* Não suporta transações complexas ou joins; consistência eventual por padrão (Strong custa o dobro); modelo de custo pode ser caro se mal dimensionado (On-Demand a $1.25/milhão de escritas pode custar milhares de dólares/mês em alta frequência constante).9  
  * *Ideal para:* Tabela de Ledger (Lançamentos) imutável com sharding.

### **4.2 Amazon Aurora PostgreSQL: A Escolha Relacional**

O Aurora desacopla computação de armazenamento, permitindo maior throughput que o PostgreSQL padrão.

* **Arquitetura:** O log de transações é enviado para uma camada de armazenamento distribuída em 3 AZs.  
* **O Problema de 5.000 TPS:** Mesmo sem gargalo de I/O de disco, o bloqueio de linha (Row Lock) em um UPDATE concorrente na mesma conta causará contenção de CPU massiva.  
* **Solução (Append-Only):** Inserir no Ledger em vez de atualizar Saldo. O Aurora lida bem com 5.000 *inserts* concorrentes se houver índices mínimos.  
* **Custo (I/O Optimized):** Para workloads de alta escrita, o custo de I/O do Aurora Standard ($0.20/milhão de requests) é proibitivo. A configuração **I/O Optimized** elimina custos de I/O em troca de um custo maior de armazenamento e instância, gerando economia de até 40% em casos de uso intensivo como este.11  
* **Trade-offs:**  
  * *Prós:* ACID completo; SQL rico para relatórios e conciliação; familiaridade para times de bancos; ecossistema robusto.  
  * *Contras:* Limite de escala vertical para escrita (um único nó Writer); recuperação de saldo em tempo real (SUM) fica lenta com o crescimento da tabela sem processos de compactação/snapshot.  
  * *Ideal para:* Tabelas de metadados, configurações e Ledgers que exigem integridade referencial forte.

### **4.3 Redis (Amazon ElastiCache): A Escolha de Velocidade**

O Redis é um armazenamento em memória (In-Memory), oferecendo latências de microssegundos.

* **Uso Estratégico:** Não deve ser o *System of Record* (SoR) devido à persistência volátil (embora existam persistências AOF/RDB, o failover pode perder dados de milissegundos recentes).13  
* **Função no Sistema:**  
  1. **Idempotência:** Armazenar chaves de transação (TransactionID) com TTL de 24h para evitar processamento duplicado instantâneo.7  
  2. **Rate Limiting:** Controlar a vazão para o mainframe.  
  3. **Cache de Saldo:** Armazenar o *Saldo Provisionado* para leitura rápida pelo orquestrador. O Redis suporta operações atômicas (INCRBY) que são perfeitas para decrementar saldos em tempo real sem locks complexos de banco de dados.  
* **Trade-offs:**  
  * *Prós:* Velocidade inigualável; operações atômicas simples.  
  * *Contras:* Risco de perda de dados; custo de RAM para grandes volumes de dados históricos.

### **4.4 ScyllaDB: A Escolha de Alta Vazão e Baixa Latência**

ScyllaDB é uma reescrita do Apache Cassandra em C++, utilizando uma arquitetura *shared-nothing* e *shard-per-core*.

* **Arquitetura:** Cada núcleo de CPU tem sua própria memória e processa suas próprias requisições, eliminando bloqueios globais e o overhead do Garbage Collector do Java (problema comum no Cassandra).14  
* **Vantagem para 5.000 TPS:** Scylla é projetado para milhões de TPS. Ele lida com escritas massivas com latência de cauda (P99) extremamente baixa e estável. Ao contrário do DynamoDB, não tem limite de 1.000 WCU por partição da mesma forma rígida (embora hot partitions ainda devam ser evitadas, o hardware subjacente é mais eficiente).  
* **Trade-offs:**  
  * *Prós:* Performance superior ao DynamoDB e Cassandra em latência/throughput; custo menor por operação em escala massiva (hardware eficiente); compatível com API do DynamoDB e Cassandra.  
  * *Contras:* Complexidade operacional maior que DynamoDB (se for auto-gerenciado, embora exista Scylla Cloud); consistência eventual por padrão (Tunable Consistency).  
  * *Ideal para:* Ledger histórico massivo e ingestão de alta velocidade se o DynamoDB se tornar muito caro.

### **4.5 CockroachDB: O SQL Distribuído (NewSQL)**

CockroachDB oferece escalabilidade horizontal (como NoSQL) com consistência forte ACID (como SQL) usando o algoritmo de consenso Raft.

* **Arquitetura:** Distribui dados em *Ranges*. Quando um Range fica "quente" (muitas escritas), o CockroachDB automaticamente o divide e rebalanceia para outros nós.  
* **Vantagem para 5.000 TPS:** Diferente do Aurora (que tem um nó de escrita), o Cockroach aceita escritas em qualquer nó. Para o problema de "Hot Account", ele ainda sofre com contenção se todas as transações tentarem atualizar a mesma linha (devido ao Raft), mas é excelente para *Ledger* distribuído geograficamente.  
* **Trade-offs:**  
  * *Prós:* Consistência Forte (Serializable Isolation) garantida, sobrevivência a falhas de região; escala horizontal de leitura e escrita.  
  * *Contras:* Latência de escrita mais alta que Dynamo/Scylla devido à coordenação do Raft (consenso); overhead de CPU.  
  * *Ideal para:* Substituição futura do DB2 como System of Record na nuvem, garantindo consistência estrita sem mainframe.

## ---

**5\. Tabela Comparativa de Motores de Dados**

A tabela abaixo sintetiza a análise para o cenário de 5.000 TPS em conta única (com as devidas estratégias de mitigação aplicadas, como sharding).

| Característica | Amazon DynamoDB | Amazon Aurora (I/O Opt) | Redis (Cluster) | ScyllaDB | CockroachDB |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Modelo** | NoSQL (Chave-Valor) | Relacional (SQL) | In-Memory (Estruturas) | NoSQL (Wide-Column) | Distributed SQL |
| **Estratégia 5k TPS** | Write Sharding (Sufixo) | Append-Only (Insert) | Nativo (INCRBY) | Sharding Automático | Range Splitting |
| **Latência Escrita** | \< 10ms (P99) | 10-20ms | \< 1ms | \< 5ms | 20-50ms (Consenso) |
| **Consistência** | Eventual (Padrão) | Forte (ACID) | Forte (Nó único) | Eventual (Tunable) | Forte (ACID Global) |
| **Custo (Alta Vazão)** | Alto (Linear/WCU) | Médio (Fixo \+ Storage) | Alto (Custo de RAM) | Baixo (Efic. Hardware) | Médio/Alto (Compute) |
| **Complexidade Ops** | Mínima (Serverless) | Baixa (Managed) | Mínima (Managed) | Média/Baixa | Média |
| **Uso Recomendado** | **Ledger / Ingestão** | **Metadados / Relatórios** | **Cache / Locks** | **Histórico Massivo** | **Novo SoR / Saldo** |

## ---

**6\. Estratégias de Convivência e Migração**

A transição do "Mainframe Monolito" para a "Nuvem Distribuída" não ocorre em um único passo. A estratégia recomendada é a do **Estrangulamento (Strangler Fig Pattern)**, onde o sistema legado é progressivamente substituído por novas implementações.6

### **6.1 O Padrão "Ledger Sombra" (Shadow Ledger)**

Para permitir que a AWS autorize transações sem consultar o DB2 a cada milissegundo, criamos um espelho autoritativo na nuvem.

#### **6.1.1 Fluxo da Transação (Happy Path)**

1. **Orquestrador (Java Microservice):** Recebe a transação de débito.  
2. **Validação de Idempotência:** Consulta o Redis. Se a chave req\_xyz já existe, retorna a resposta salva.  
3. **Validação de Saldo:**  
   * Consulta a tabela Saldo\_Snapshot (DynamoDB/Cockroach).  
   * Calcula o Saldo\_Disponivel subtraindo provisões recentes do cache Redis ou tabela de movimentos recentes.  
   * Se Saldo \> Transação, prossegue.  
4. **Reserva de Crédito (Provisionamento):** Insere um registro de "Débito Pendente" no DynamoDB (com Write Sharding) e/ou decrementa o saldo provisório no Redis.  
5. **Confirmação ao Usuário:** Retorna "Sucesso" ou "Em Processamento".  
6. **Envio Assíncrono:** Publica o evento TransactionCreated em um tópico Kafka ou Kinesis Data Stream.

#### **6.1.2 Sincronização com o Mainframe (Barragem)**

O mainframe não suporta 5.000 TPS de atualizações na mesma conta. Portanto, a AWS deve atuar como uma "barragem".

* **Consumer de Barragem:** Um serviço lê do Kinesis em janelas de tempo (ex: 500ms ou 1 segundo).  
* **Agregação (Micro-batching):** O serviço soma todas as transações da janela para a conta X.  
  * Exemplo: 2.000 créditos de R$ 10 \+ 1.000 débitos de R$ 5 \= Saldo Líquido de \+R$ 15.000.  
* **Atualização Atômica:** O serviço envia *uma única* transação para o DB2: UPDATE CONTA SET SALDO \= SALDO \+ 15000\.  
* **Resultado:** O mainframe processa 1 TPS por conta em vez de 3.000, eliminando a contenção de locks.4

#### **6.1.3 Fluxos Compensatórios e Reconciliação**

O que acontece se a AWS autorizar, mas o mainframe rejeitar (ex: conta bloqueada administrativamente no último segundo)?

1. **Evento de Rejeição:** O DB2 retorna erro para o Consumer de Barragem.  
2. **Saga de Compensação:** O Consumer publica um evento TransactionRejected.  
3. **Orquestrador:**  
   * Lê o evento.  
   * Insere um "Crédito Compensatório" (Estorno) no Ledger da AWS.  
   * Remove a reserva de saldo.  
   * Notifica o cliente (Push Notification/Email) sobre a falha na efetivação.  
4. **Conciliação Diária:** Um processo batch (Spark/Glue) compara o Ledger do DB2 com o Ledger da AWS para identificar discrepâncias de centavos ou transações perdidas, gerando relatórios para a contabilidade.

## ---

**7\. Implementação Técnica: O Engenheiro de Dados em Ação**

Na prática, a implementação dessa arquitetura em Java exige padrões robustos.

### **7.1 Orquestrador e Máquina de Estados**

Utilizar frameworks como Spring Boot com suporte a Sagas (ex: Axon ou implementação customizada com Kafka). O orquestrador não deve manter estado em memória da aplicação; o estado da transação (PENDING, SENT\_TO\_MAINFRAME, COMPLETED, FAILED) deve ser persistido no DynamoDB/Aurora.

### **7.2 Gerenciamento de Threads e Conexões**

Para 5.000 TPS, o modelo thread-per-request do Tomcat tradicional pode sofrer com overhead de Context Switching.

* **Recomendação:** Utilizar programação reativa (Project Reactor / Spring WebFlux) ou Virtual Threads (Java 21+). Isso permite que o serviço de I/O (chamar Dynamo, chamar Kafka) não bloqueie threads do sistema operacional, maximizando a vazão com menor consumo de CPU.

### **7.3 Tuning do Producer Kafka**

Para a ingestão no Kafka/Kinesis ser eficiente:

* batch.size: Aumentar para permitir envio em lotes (ex: 64KB ou 128KB).  
* linger.ms: Configurar para 5-10ms. Isso força o producer a esperar um pouco para agrupar mensagens antes de enviar, reduzindo IOPS de rede e aumentando o throughput total em detrimento de uma latência minúscula.15

## ---

**8\. Conclusão e Roadmap Evolutivo**

A análise demonstra que a tentativa de estender o modelo síncrono do DB2 para suportar 5.000 TPS em contas concentradoras é uma falácia arquitetural fadada ao gargalo de contenção de recursos. A solução reside na **hibridização assíncrona**.

**Recomendações Finais:**

1. **Adote o DynamoDB com Write Sharding** como o Ledger de alta velocidade para ingestão (Journaling), utilizando sua previsibilidade de latência e integração serverless.  
2. **Utilize o Redis** como a camada de controle de concorrência (Semaforo) e idempotência, protegendo os sistemas de persistência.  
3. **Implemente a Barragem de Micro-batching** entre a nuvem e o mainframe. Isso preserva o investimento no Core Banking DB2 enquanto libera a inovação nos canais digitais.  
4. **Considere o Aurora I/O Optimized** apenas se houver necessidade crítica de queries relacionais complexas sobre os dados quentes; caso contrário, o custo-benefício pende para NoSQL.  
5. **Avalie ScyllaDB ou CockroachDB** como o próximo passo da evolução (fase 2), visando substituir o DB2 como System of Record definitivo na nuvem, eliminando a dependência do mainframe a longo prazo.

Esta arquitetura fornece a elasticidade necessária para suportar picos de Black Friday e a robustez exigida para a integridade financeira, respeitando as características físicas de cada tecnologia envolvida.

## ---

**Referências Bibliográficas Citadas no Texto**

* 1 Infosys. *Four Design Patterns to Modernize Core Banking*.  
* 2 Google Cloud. *Hot Rows, Cool Solutions: Architecting for High Throughput Payment Systems*.  
* 2 Google Cloud. *Architecting for High Throughput: Append-Only Patterns*.  
* 4 Hacker News Discussion. *Postgres Scaling and Batch Updates*.  
* 5 TopicPartition. *Postgres PubSub Queue Benchmarks and Batching*.  
* 15 CodePerfector. *Using Kafka Producers and Consumers Properly*.  
* 16 AWS Documentation. *Best Practices for Using Partition Keys in DynamoDB*.  
* 8 Medium. *DynamoDB Data Modeling Fundamentals and Write Sharding*.  
* 13 StackOverflow. *DynamoDB vs Redis for Persistent Storage*.  
* 6 Devox Software. *Legacy Modernization in Banking: The Strangler Pattern*.  
* 10 Dynobase. *DynamoDB Pricing Calculator and Request Units*.  
* 9 AWS Documentation. *DynamoDB Provisioned Capacity Pricing*.  
* 11 CloudFix. *Aurora I/O Optimized vs Standard Pricing*.  
* 2 Medium. *Hot Row Contention in Payment Systems*.  
* 3 Fabio Akita. *Discutindo sobre Banco de Dados \- Consistência e ACID*.  
* 7 AWS Builders' Library. *Making Retries Safe with Idempotent APIs*.  
* 8 Medium. *Handling High Throughput with Sharding Strategies*.  
* 14 InterSystems. *Database Sharding Strategies and Best Practices*.  
* 12 AWS Blog. *Improve Aurora PostgreSQL Throughput with Optimized Reads*.

---

*(Nota: Este relatório foi elaborado assumindo o papel de um Especialista em Engenharia de Dados e Arquitetura de Soluções, conforme solicitado, mantendo o rigor técnico e a profundidade necessária para a tomada de decisão em nível corporativo.)*

#### **Works cited**

1. Four design patterns to innovate around a bank's core \- Infosys, accessed January 12, 2026, [https://www.infosys.com/iki/perspectives/four-design-patterns.html](https://www.infosys.com/iki/perspectives/four-design-patterns.html)  
2. Hot Rows, Cool Solutions: Architecting for High-Throughput Payment Systems | by Szabolcs Rozsnyai | Google Cloud \- Medium, accessed January 12, 2026, [https://medium.com/google-cloud/hot-rows-cool-solutions-architecting-for-high-throughput-payment-systems-b0ae8bb2ec52](https://medium.com/google-cloud/hot-rows-cool-solutions-architecting-for-high-throughput-payment-systems-b0ae8bb2ec52)  
3. Discutindo sobre Banco de Dados \- Dos primórdios a Big Data, accessed January 12, 2026, [https://www.youtube.com/watch?v=Bfm3Ms2cTg0\&t=5212s](https://www.youtube.com/watch?v=Bfm3Ms2cTg0&t=5212s)  
4. Kafka is Fast – I'll use Postgres \- Hacker News, accessed January 12, 2026, [https://news.ycombinator.com/item?id=45747018](https://news.ycombinator.com/item?id=45747018)  
5. Kafka is fast \-- I'll use Postgres \- TopicPartition, accessed January 12, 2026, [https://topicpartition.io/blog/postgres-pubsub-queue-benchmarks](https://topicpartition.io/blog/postgres-pubsub-queue-benchmarks)  
6. Legacy modernization in Banking & Finance: Eight-Pillar Playbook for CTOs, accessed January 12, 2026, [https://devoxsoftware.com/blog/legacy-modernization-in-banking-finance-eight-pillar-playbook-for-ctos/](https://devoxsoftware.com/blog/legacy-modernization-in-banking-finance-eight-pillar-playbook-for-ctos/)  
7. Making retries safe with idempotent APIs \- AWS, accessed January 12, 2026, [https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-apis/](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-apis/)  
8. DynamoDB Data Modeling Fundamentals | Medium, accessed January 12, 2026, [https://medium.com/@joudwawad/dynamodb-data-modeling-fundamentals-9cfdf7f4dcb6](https://medium.com/@joudwawad/dynamodb-data-modeling-fundamentals-9cfdf7f4dcb6)  
9. Amazon DynamoDB pricing for provisioned capacity – Serverless ..., accessed January 12, 2026, [https://aws.amazon.com/dynamodb/pricing/provisioned/](https://aws.amazon.com/dynamodb/pricing/provisioned/)  
10. DynamoDB Pricing & Cost Calculator (Free Tool) \- Dynobase, accessed January 12, 2026, [https://dynobase.dev/dynamodb-pricing-calculator/](https://dynobase.dev/dynamodb-pricing-calculator/)  
11. Aurora I/O-Optimized vs Standard: Save 30-40% on AWS Database Costs (2026 Guide), accessed January 12, 2026, [https://cloudfix.com/blog/aurora-io-optimized-vs-standard/](https://cloudfix.com/blog/aurora-io-optimized-vs-standard/)  
12. Improve Aurora PostgreSQL throughput by up to 165% and price-performance ratio by up to 120% using Optimized Reads on AWS Graviton4-based R8gd instances, accessed January 12, 2026, [https://aws.amazon.com/blogs/database/improve-aurora-postgresql-throughput-by-up-to-165-and-price-performance-ratio-by-up-to-120-using-optimized-reads-on-aws-graviton4-based-r8gd-instances/](https://aws.amazon.com/blogs/database/improve-aurora-postgresql-throughput-by-up-to-165-and-price-performance-ratio-by-up-to-120-using-optimized-reads-on-aws-graviton4-based-r8gd-instances/)  
13. DynamoDB vs Redis for persistent storage? \- Stack Overflow, accessed January 12, 2026, [https://stackoverflow.com/questions/56870326/dynamodb-vs-redis-for-persistent-storage](https://stackoverflow.com/questions/56870326/dynamodb-vs-redis-for-persistent-storage)  
14. Mastering Database Sharding: Strategies and Best Practices | InterSystems, accessed January 12, 2026, [https://www.intersystems.com/resources/mastering-database-sharding-strategies-and-best-practices/](https://www.intersystems.com/resources/mastering-database-sharding-strategies-and-best-practices/)  
15. Using Kafka Producers and Consumers properly | by Wayne Menezes \- Medium, accessed January 12, 2026, [https://medium.com/@codeperfector/using-kafka-producers-and-consumers-properly-45e63689511a](https://medium.com/@codeperfector/using-kafka-producers-and-consumers-properly-45e63689511a)  
16. Using write sharding to distribute workloads evenly in your DynamoDB table, accessed January 12, 2026, [https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html)