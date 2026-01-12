# **Relatório de Pesquisa Avançada em Engenharia de Dados: Arquiteturas de Alta Vazão para Sistemas Transacionais Bancários**

## **1\. Resumo Executivo e Definição do Escopo**

Este relatório técnico foi elaborado em resposta à solicitação de um engenheiro especialista em dados, com o objetivo de desenhar uma solução robusta para o problema de "Hot Key" (Conta Quente) e alta vazão (Transactions Per Second \- TPS) em um contexto bancário brasileiro. O cenário envolve transações de crédito e débito, processadas por microserviços Java, com a necessidade crítica de modelar fluxos compensatórios, tabelas de saldos e ledgers (livros-razão).

O documento aborda duas vertentes arquiteturais distintas solicitadas: a integração de um legado IBM DB2 (mainframe/non-mainframe) com a AWS, e a criação de um sistema "Greenfield" totalmente nativo na nuvem (AWS). A análise é fundamentada em princípios de engenharia de confiabilidade (SRE), consistência de dados (ACID vs. BASE) e padrões distribuídos avançados como o framework "Orpheus" e estratégias de *sharding* de banco de dados.

A premissa central deste estudo é que em sistemas financeiros, a integridade dos dados (zero perda, zero pagamento duplicado) é inegociável. A latência e a disponibilidade, embora críticas, submetem-se à consistência. O relatório detalha como alcançar TPS na ordem de dezenas de milhares em uma única conta lógica através de técnicas de decomposição de escritas, *locking* otimista e pessimista, e otimização de I/O em bancos de dados relacionais e NoSQL.

## ---

**2\. Fundamentos Teóricos da Alta Concorrência em Sistemas Financeiros**

### **2.1 O Problema da "Conta Quente" (Hot Key)**

No cerne do desafio de TPS em uma única conta bancária reside o problema de contenda de bloqueio (*lock contention*). Em um banco de dados relacional tradicional, para garantir a consistência ACID (Atomicidade, Consistência, Isolamento, Durabilidade), uma transação que atualiza o saldo de uma conta deve adquirir um bloqueio exclusivo (mutex) na linha correspondente àquela conta.

Se a conta X recebe 5.000 requisições de crédito por segundo, e cada transação leva 2 milissegundos para ser concluída (I/O de disco, commit de log, round-trip de rede), o banco de dados serializa essas operações. Matematicamente, o throughput máximo teórico é o inverso da latência de retenção do bloqueio:

$$TPS\_{max} \= \\frac{1}{Latencia\_{lock}}$$

Com uma latência de 2ms, o limite físico é de 500 TPS, independentemente da potência da CPU ou da memória do servidor. Para atingir escalas superiores, a engenharia deve transcender o modelo de bloqueio serializado em uma única linha.1

### **2.2 Idempotência como Pilar Arquitetural**

Em sistemas distribuídos, a comunicação entre microserviços (Java) e bancos de dados ou APIs externas é inerentemente não confiável. O "Problema dos Dois Generais" dita que não podemos ter certeza se uma mensagem foi perdida no envio, no processamento ou na resposta.

O framework "Orpheus", analisado neste estudo, estabelece a **Chave de Idempotência** como o elemento central da arquitetura. Esta chave não é apenas um identificador de deduplicação; ela serve como chave de particionamento (*shard key*) para o banco de dados.3

* **Cardinalidade e Distribuição:** A escolha da chave de idempotência deve garantir alta cardinalidade (ex: UUID v4) para assegurar uma distribuição uniforme dos dados entre os shards do banco de dados, evitando "hot spots" de escrita.  
* **Ciclo de Vida do Bloqueio:** A chave de idempotência é utilizada para adquirir um *lease* (bloqueio com tempo de expiração) no banco de dados. Isso impede que cliques duplos do usuário ou retentativas automáticas de redes neurais (como em malhas de serviço Istio/Envoy) gerem processos paralelos de débito para a mesma intenção de pagamento.

### **2.3 O Ciclo de Vida da Transação em Três Fases (Padrão Orpheus)**

Para mitigar inconsistências, especialmente em cenários de crédito provisionado (onde há uma reserva de valor seguida de uma captura ou cancelamento), adota-se um ciclo de vida estrito de três fases 3:

1. **Pré-RPC (Intenção/Provisionamento):** O microserviço Java grava a intenção da transação no banco de dados. Isso cria um registro de "Pendente" e adquire o lock na chave de idempotência. Nenhuma chamada de rede externa ocorre aqui.  
2. **RPC (Execução Remota):** O sistema comunica-se com o sistema externo (ex: Gateway de Pagamento, Banco Central para Pix). **Crucialmente, nenhuma conexão de banco de dados é mantida aberta durante esta fase.** Isso previne a exaustão do pool de conexões (Connection Pool Starvation) caso o serviço externo sofra latência.  
3. **Pós-RPC (Materialização/Confirmação):** Com a resposta do serviço externo, o sistema abre uma nova transação de banco de dados para atualizar o estado para "Sucesso" ou "Falha" e liberar o lock da chave de idempotência.

## ---

**3\. Cenário 1: Integração Híbrida (IBM DB2 Legado \+ AWS)**

Neste cenário, assumimos a existência de um sistema legado robusto (IBM DB2, possivelmente em mainframe ou AIX) que detém o "Golden Record" dos clientes, mas que não suporta a elasticidade necessária para picos de TPS modernos ou cujos custos de MIPS (Million Instructions Per Second) são proibitivos para consultas massivas.

### **3.1 Estratégia de "Strangler Fig" e Offloading**

A abordagem recomendada não é a substituição imediata, mas o padrão "Strangler Fig" (Figueira Estranguladora), onde o novo sistema na AWS assume gradualmente responsabilidades.

#### **3.1.1 Offloading de Leitura (Read Replicas na Nuvem)**

O primeiro passo para aliviar o DB2 é remover o tráfego de leitura (consultas de saldo, extrato).

* **Mecanismo:** Utilização de ferramentas de CDC (Change Data Capture) como IBM InfoSphere Data Replication ou conectores de Kafka (Debezium para DB2).  
* **Fluxo:** O DB2 grava no seu Transaction Log. O conector CDC lê o log e publica eventos ("Saldo Alterado", "Nova Transação") em um tópico Kafka (ex: Amazon MSK).5  
* **Consumo:** Um cluster de consumidores Java na AWS lê do Kafka e atualiza uma base de leitura de alta performance, como Amazon DynamoDB ou Amazon Aurora.  
* **Latência de Replicação:** O engenheiro deve projetar a API de consulta para tolerar "consistência eventual". Se o usuário fizer uma transação e imediatamente consultar o saldo, o sistema pode precisar ler do DB2 (fallback) ou verificar a latência de replicação do Kafka.

#### **3.1.2 Offloading de Escrita (Buffer e Sincronização Assíncrona)**

Para alta vazão de escrita que excede a capacidade do DB2, o sistema AWS atua como um "Buffer de Alta Velocidade".

* **Crédito à Vista:** A transação é processada e finalizada na AWS (Aurora/DynamoDB). O saldo "nuvem" é atualizado instantaneamente.  
* **Sincronização (Write-Behind):** Um processo assíncrono (Connector Sink ou Lambda) consolida as transações e as envia para o DB2 em lote (*batch*), ou via filas de mensagens (IBM MQ integrando com SQS).  
* **Risco:** O risco de "Split Brain" (cérebro dividido) onde o saldo no DB2 e na AWS divergem. Para mitigar, a AWS deve ser a "Fonte da Verdade" (*System of Record*) para os tipos de transação migrados, enquanto o DB2 torna-se um espelho para fins regulatórios e de legado.7

### **3.2 Desafios de Conectividade e Latência Híbrida**

A latência de rede entre o data center on-premise e a região da AWS (ex: sa-east-1) é um fator físico limitante.

* **Direct Connect:** É mandatório o uso de AWS Direct Connect para garantir largura de banda dedicada e latência previsível, evitando a variabilidade da internet pública.  
* **Padrão de Circuit Breaker:** Os microserviços Java devem implementar *Circuit Breakers* (ex: Resilience4j). Se o DB2 ou o link Direct Connect falharem, o sistema deve degradar graciosamente (ex: negar transações que exigem validação síncrona no legado, mas aceitar transações que podem ser processadas puramente na AWS).3

## ---

**4\. Cenário 2: Sistema Nativo na Nuvem (AWS) \- Modelagem Avançada**

Neste cenário, desenhamos um sistema do zero ("Greenfield") na AWS, sem as amarras do legado, focado puramente em performance e escalabilidade.

### **4.1 Modelagem de Dados: Relacional vs. NoSQL**

A escolha entre Amazon Aurora PostgreSQL e Amazon DynamoDB é a decisão mais crítica de engenharia, com implicações profundas em custo e consistência.

#### **4.1.1 Amazon Aurora PostgreSQL: A Escolha pela Integridade**

Para um sistema de *Ledger* (Razão) e *Saldo* (Balance), o modelo relacional oferece garantias ACID robustas e integridade referencial, essenciais para auditoria.

Tabela de Ledger (Lançamentos):  
A tabela de lançamentos deve ser imutável ("Append-Only").

SQL

CREATE TABLE transaction\_ledger (  
    transaction\_id UUID PRIMARY KEY,  
    idempotency\_key UUID NOT NULL UNIQUE,  
    debit\_account\_id UUID NOT NULL,  
    credit\_account\_id UUID NOT NULL,  
    amount DECIMAL(19,4) NOT NULL,  
    currency CHAR(3) DEFAULT 'BRL',  
    transaction\_type VARCHAR(20) NOT NULL, \-- 'CREDIT', 'DEBIT', 'PROVISION'  
    status VARCHAR(20) NOT NULL, \-- 'PENDING', 'COMPLETED', 'FAILED'  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

Otimização HOT (Heap Only Tuple) para Alta Vazão:  
Em tabelas de saldo (account\_balances), atualizações frequentes geram "bloat" (inchaço) e overhead de VACCUM no PostgreSQL.

* **Anti-padrão:** Indexar colunas que são frequentemente atualizadas. Se a coluna last\_updated for indexada, cada atualização de saldo exigirá uma reescrita no índice, impedindo a otimização HOT.  
* **Tuning de fillfactor:** O padrão de fillfactor é 100%. Para tabelas de saldo com alta taxa de update, deve-se reduzir para 70-80%. Isso deixa espaço na página de dados para que a nova versão da linha seja gravada no mesmo bloco, permitindo que o Postgres atualize o ponteiro sem tocar nos índices, reduzindo drasticamente o I/O.8

Custo de I/O no Aurora:  
O modelo de cobrança do Aurora Standard cobra por I/O (\~$0.20 por milhão de requisições). Um sistema de 5.000 TPS gera bilhões de I/Os mensais, tornando o custo proibitivo.

* **Recomendação:** Utilizar **Aurora I/O-Optimized**. Embora o custo de armazenamento e instância seja maior (\~30-40%), o custo de I/O é zero. Para cargas de trabalho de pagamentos intensivas em escrita, isso resulta em uma economia de 40% ou mais no TCO (Total Cost of Ownership).9

#### **4.1.2 Amazon DynamoDB: A Escolha pela Escala Infinita**

Para a resolução extrema do problema de TPS, o DynamoDB oferece latência previsível independente do volume de dados, mas exige modelagem de acesso precisa (Single Table Design).

Estratégia de Sharding de Saldo (Balance Sharding):  
Para superar o limite de escrita em uma única partição (aprox. 1000 WCU ou Writes/segundo), aplicamos o padrão de Write Sharding na conta quente.1

* **Modelo:** Em vez de uma linha de saldo, a conta X possui N sub-contas (X\_1, X\_2,..., X\_N).  
* **Escrita:** O microserviço escolhe aleatoriamente um shard X\_i para debitar ou creditar. UPDATE Accounts SET balance \= balance \+ :amount WHERE account\_id \= :X\_i. Isso divide a contenda de bloqueio por N.  
* **Leitura:** Para obter o saldo total, o sistema deve ler todos os shards e somá-los (Scatter-Gather).  
  * *Trade-off:* Escrita ultra-rápida, leitura mais custosa e lenta. Ideal para contas de grandes varejistas onde o recebimento é massivo e a leitura do saldo exato em tempo real é menos frequente ou pode ser servida por um cache.

## ---

**5\. Estruturas de Dados e Algoritmos para Resolução de TPS**

### **5.1 O Orquestrador e a Validação de Fluxos**

O orquestrador (microserviço Java) deve atuar como uma máquina de estados finitos. Utilizando o padrão **Saga** (Orquestrada, não Coreografada, para maior controle em pagamentos), ele gerencia os fluxos de crédito à vista e provisionado.

* Validação de Saldo (Provisionamento):  
  Para evitar Overdraft (saldo negativo) em alta concorrência, não se deve ler o saldo e depois escrever (Time-of-Check to Time-of-Use race condition).  
  Deve-se usar a instrução atômica no banco de dados:  
  SQL  
  UPDATE account\_balances  
  SET balance \= balance \- :amount, reserved\_balance \= reserved\_balance \+ :amount  
  WHERE account\_id \= :id AND (balance \- :amount) \>= 0;

  Se o banco retornar que zero linhas foram afetadas, a transação falha por saldo insuficiente. Esta operação é atômica e segura sob qualquer nível de concorrência.12

### **5.2 Locking: Pessimista vs. Otimista**

A escolha do mecanismo de bloqueio define o comportamento do sistema sob carga máxima.

| Característica | Locking Pessimista (SELECT... FOR UPDATE) | Locking Otimista (Versionamento @Version) |
| :---- | :---- | :---- |
| **Mecanismo** | Bloqueia o recurso no início da transação. Ninguém mais lê ou escreve. | Lê, processa e tenta salvar verificando se a versão mudou. |
| **Cenário Ideal** | Alta contenda (muitos tentando acessar a mesma conta). Garante ordem. | Baixa a média contenda. |
| **Comportamento na Hot Key** | **Fila de Espera.** As transações enfileiram-se no banco. Risco de *timeout* da aplicação se a fila for longa. | **Falha Rápida (Fail-Fast).** A maioria das transações falhará com OptimisticLockException. Exige retentativa complexa na aplicação. |
| **Recomendação** | **Recomendado para o "Critical Section" curto.** Manter a transação o mais breve possível (somente atualização de saldo). 14 | Recomendado para atualização de dados cadastrais, não para saldo financeiro de alta frequência. |

Para a conta de alta vazão (Hot Key), o Locking Pessimista é geralmente preferível *dentro de uma transação muito curta*, pois o custo de gerenciar milhares de exceções de concorrência otimista (retries) na camada de aplicação (Java) e rede é superior ao custo de espera ordenada no banco de dados, desde que o banco seja dimensionado corretamente.16

## ---

**6\. Integração Assíncrona com Apache Kafka**

A utilização de Kafka é mandatória para desacoplar a ingestão da transação do processamento do ledger, permitindo "Backpressure" (controle de fluxo) em momentos de pico.

### **6.1 Garantias de Entrega e Ordem**

* **Particionamento Semântico:** As mensagens no Kafka devem usar o account\_id como chave de partição. Isso garante que todas as transações de uma mesma conta caiam na mesma partição e sejam consumidas em ordem cronológica por um único consumidor, preservando a sequência de débitos e créditos.18  
* **Batch Listeners:** O consumidor Java (Spring Kafka) deve ser configurado para processar lotes (batch listeners). Em vez de fazer 500 UPDATES individuais no banco, o consumidor pega um lote de 500 mensagens, agrupa por conta, e faz um *bulk update* ou insere no ledger em lote. Isso reduz drasticamente o overhead de rede e transação.20

### **6.2 O Padrão "Transactional Outbox"**

Para garantir que a transação financeira e o evento "Transação Realizada" enviado ao Kafka estejam sincronizados (atomicidade dual), usa-se o padrão Outbox.21

1. A aplicação grava o débito na tabela BALANCE e o evento na tabela OUTBOX na mesma transação ACID do banco de dados.  
2. Um conector (CDC/Debezium) lê a tabela OUTBOX e publica no Kafka.  
   Isso garante Exactly-Once Semantics (semântica de exatamente uma vez) na perspectiva de emissão de eventos, crucial para sistemas de notificação e downstream.

## ---

**7\. Análise Comparativa de Custos e Infraestrutura**

### **7.1 Aurora PostgreSQL (I/O Optimized)**

* **Vantagens:** Compatibilidade SQL completa, integridade referencial, ecossistema maduro, facilidade de contratação de profissionais.  
* **Desvantagens:** Escalabilidade vertical de escrita (limite de um nó Master), necessidade de tuning fino (autovacuum, shared\_buffers).  
* **Custo:** Previsível em instâncias reservadas, mas com degrau de custo alto para I/O Optimized.10

### **7.2 Amazon DynamoDB**

* **Vantagens:** Escalabilidade de escrita horizontal praticamente infinita, modelo Serverless (sem gestão de OS), integração nativa com Lambda e Streams.  
* **Desvantagens:** Curva de aprendizado (NoSQL, Single Table Design), consistência forte custa o dobro (2x WRU/RRU), falta de queries complexas para relatórios (Analytics exige export para S3/Athena).  
* **Custo:** Modelo *Pay-per-request* excelente para cargas variáveis, mas linearmente caro em volumes massivos constantes (Provisioned Capacity é mais barato mas exige gerenciamento).22

### **7.3 Tabela Comparativa de Decisão**

| Critério | Legado Modernizado (DB2+AWS) | Cloud Native (Aurora Postgres) | Cloud Native (DynamoDB) |
| :---- | :---- | :---- | :---- |
| **Complexidade de Migração** | Média (Strangler Fig) | Alta (Reescrita) | Muito Alta (Mudança de Paradigma) |
| **Limite de TPS (Single Row)** | Baixo (Limitado pelo Mainframe) | Médio (Limitado pelo Lock) | Alto (Com Sharding de Aplicação) |
| **Consistência** | Eventual (Entre on-prem e cloud) | Forte (ACID Local) | Forte (ACID Item/Transact) |
| **Custo Operacional** | Alto (Licenças DB2 \+ AWS) | Médio (Gestão RDS) | Baixo (Serverless) |
| **Flexibilidade de Query** | Baixa (Legado rígido) | Alta (SQL) | Baixa (Chave-Valor) |

## ---

**8\. Detalhamento Técnico da Implementação (Java Microservices)**

### **8.1 Gerenciamento de Conexões (HikariCP)**

A configuração do pool de conexões é crítica.

* **Tamanho do Pool:** Não deve ser muito grande. PoolSize \= (Core\_Count \* 2\) \+ Effective\_Spindle\_Count. Para um servidor de 16 cores, um pool de 30-40 conexões é frequentemente mais performático que um de 100, pois reduz a troca de contexto de CPU (*Context Switching*) no banco de dados.  
* **Connection Timeout:** Deve ser agressivo. Se uma conexão não for obtida em 250ms, falhe rápido. Isso impede que threads do servidor de aplicação fiquem presas esperando banco, o que levaria a um efeito cascata.

### **8.2 Otimizações da JVM**

Para sistemas de baixa latência e alta vazão:

* **Garbage Collector:** Utilizar **ZGC** (disponível no JDK 11/17+) ou **Shenandoah**. Eles são projetados para pausas de GC sub-milissegundo, essenciais para evitar "lags" de latência que causam timeouts de transação distribuída.  
* **Memória:** Evitar alocação excessiva de objetos efêmeros no *Hot Path* da transação. Preferir tipos primitivos e estruturas de dados reutilizáveis onde possível.

## ---

**9\. Conclusão e Recomendação**

Com base na análise profunda do histórico de conversação, dos requisitos de crédito à vista e provisionado, e das limitações de concorrência, a recomendação de engenharia para o cenário **"Greenfield na AWS"** (Ideia 2\) é a mais viável a longo prazo para sustentar alta TPS com segurança.

Recomenda-se uma arquitetura **híbrida poliglota na nuvem**:

1. **Ledger e Metadados:** Amazon Aurora PostgreSQL (I/O Optimized) para a integridade relacional e auditoria complexa.  
2. **Saldos de Alta Frequência ("Hot Wallets"):** Amazon DynamoDB ou uma tabela Aurora com *Internal Sharding* (Sub-contas) e *tuning* agressivo de fillfactor e HOT updates.  
3. **Orquestração:** Java Microservices com Spring Boot, utilizando o padrão Orpheus de 3 fases e Kafka para desacoplamento e consistência eventual de sistemas satélites (notificações, fraude, analytics).

Para a **"Ideia 1" (Legado DB2)**, a estratégia deve ser estritamente de *offloading*. O DB2 não deve estar no caminho crítico da transação de alta velocidade (autorização). Ele deve receber as transações consolidadas assincronamente ("Post-Booking"), atuando como repositório legal final, enquanto a AWS processa a autorização em tempo real.

Esta arquitetura equilibra a necessidade matemática de serialização para consistência de saldo com a elasticidade horizontal necessária para suportar o crescimento exponencial do volume de pagamentos digitais no Brasil.

---

Referências de Pesquisa Incorporadas:  
3 \- Padrão Orpheus e Sharding por Chave de Idempotência.  
8 \- Otimizações HOT e Fillfactor em PostgreSQL.  
1 \- Estratégias de Sharding de Contas Quentes (Sub-contas e Filas).  
9 \- Análise de Custos AWS Aurora I/O Optimized.  
5 \- Padrões de Integração e Offloading Mainframe.  
18 \- Otimizações de Kafka e Batch Processing.  
14 \- Análise de Locking Pessimista vs. Otimista.

#### **Works cited**

1. Hot Rows, Cool Solutions: Architecting for High-Throughput Payment Systems | by Szabolcs Rozsnyai | Google Cloud \- Medium, accessed January 12, 2026, [https://medium.com/google-cloud/hot-rows-cool-solutions-architecting-for-high-throughput-payment-systems-b0ae8bb2ec52](https://medium.com/google-cloud/hot-rows-cool-solutions-architecting-for-high-throughput-payment-systems-b0ae8bb2ec52)  
2. Handling Hot Balances • Blnk Developer Documentation, accessed January 12, 2026, [https://docs.blnkfinance.com/guides/hot-balances](https://docs.blnkfinance.com/guides/hot-balances)  
3. Discutindo sobre Banco de Dados \- Dos primórdios a Big Data, accessed January 12, 2026, [https://www.youtube.com/watch?v=Bfm3Ms2cTg0](https://www.youtube.com/watch?v=Bfm3Ms2cTg0)  
4. Avoiding Double Payments in a Distributed Payments System | by ..., accessed January 12, 2026, [https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb)  
5. Integration architectures between mainframe and AWS for coexistence | Migration & Modernization, accessed January 12, 2026, [https://aws.amazon.com/blogs/migration-and-modernization/integration-architectures-between-mainframe-and-aws-for-coexistence/](https://aws.amazon.com/blogs/migration-and-modernization/integration-architectures-between-mainframe-and-aws-for-coexistence/)  
6. Using mainframe data to build cloud native services with AWS | AWS Architecture Blog, accessed January 12, 2026, [https://aws.amazon.com/blogs/architecture/mainframe-offloading-and-modernization-using-mainframe-data-to-build-cloud-native-services-with-aws/](https://aws.amazon.com/blogs/architecture/mainframe-offloading-and-modernization-using-mainframe-data-to-build-cloud-native-services-with-aws/)  
7. From Mainframe to AWS Cloud: A comprehensive mapping guide – Part 2 (Databases), accessed January 12, 2026, [https://aws.amazon.com/blogs/migration-and-modernization/from-mainframe-to-aws-cloud-a-comprehensive-mapping-guide-part-2-databases/](https://aws.amazon.com/blogs/migration-and-modernization/from-mainframe-to-aws-cloud-a-comprehensive-mapping-guide-part-2-databases/)  
8. HOT updates in PostgreSQL for better performance | CYBERTEC ..., accessed January 12, 2026, [https://www.cybertec-postgresql.com/en/hot-updates-in-postgresql-for-better-performance/](https://www.cybertec-postgresql.com/en/hot-updates-in-postgresql-for-better-performance/)  
9. Amazon Aurora Pricing \- AWS, accessed January 12, 2026, [https://aws.amazon.com/rds/aurora/pricing/](https://aws.amazon.com/rds/aurora/pricing/)  
10. Aurora I/O-Optimized vs Standard: Save 30-40% on AWS Database Costs (2026 Guide), accessed January 12, 2026, [https://cloudfix.com/blog/aurora-io-optimized-vs-standard/](https://cloudfix.com/blog/aurora-io-optimized-vs-standard/)  
11. Kafka performance: 7 critical best practices \- NetApp Instaclustr, accessed January 12, 2026, [https://www.instaclustr.com/education/apache-kafka/kafka-performance-7-critical-best-practices/](https://www.instaclustr.com/education/apache-kafka/kafka-performance-7-critical-best-practices/)  
12. Handle account balance during concurrent transactions \- Stack Overflow, accessed January 12, 2026, [https://stackoverflow.com/questions/74993419/handle-account-balance-during-concurrent-transactions](https://stackoverflow.com/questions/74993419/handle-account-balance-during-concurrent-transactions)  
13. Concurrency and Consistency: Juggling Multiple Users Without Missing a Beat, accessed January 12, 2026, [https://dev.to/isaactony/concurrency-and-consistency-juggling-multiple-users-without-missing-a-beat-2np5](https://dev.to/isaactony/concurrency-and-consistency-juggling-multiple-users-without-missing-a-beat-2np5)  
14. accessed January 12, 2026, [https://www.ibm.com/docs/en/rational-clearquest/10.0.7?topic=clearquest-optimistic-pessimistic-record-locking\#:\~:text=Overview%20of%20optimistic%20and%20pessimistic,locked%20while%20it%20is%20edited](https://www.ibm.com/docs/en/rational-clearquest/10.0.7?topic=clearquest-optimistic-pessimistic-record-locking#:~:text=Overview%20of%20optimistic%20and%20pessimistic,locked%20while%20it%20is%20edited)  
15. Locking Strategies in Databases: Optimistic vs Pessimistic Approaches | Fernando Pires, accessed January 12, 2026, [https://piresfernando.com/blog/optimistic-vs-pessimistic-lock](https://piresfernando.com/blog/optimistic-vs-pessimistic-lock)  
16. Optimistic vs. Pessimistic locking \- Stack Overflow, accessed January 12, 2026, [https://stackoverflow.com/questions/129329/optimistic-vs-pessimistic-locking](https://stackoverflow.com/questions/129329/optimistic-vs-pessimistic-locking)  
17. From Chaos to Order: The Importance of Concurrency Control within the Database | maa, accessed January 12, 2026, [https://blogs.oracle.com/maa/from-chaos-to-order-the-importance-of-concurrency-control-within-the-database-2-of-6](https://blogs.oracle.com/maa/from-chaos-to-order-the-importance-of-concurrency-control-within-the-database-2-of-6)  
18. Ensuring Message Ordering in Kafka: Strategies and Configurations | Baeldung, accessed January 12, 2026, [https://www.baeldung.com/kafka-message-ordering](https://www.baeldung.com/kafka-message-ordering)  
19. Kafka Producers Explained: Partitioning, Batching, and Reliability \- DEV Community, accessed January 12, 2026, [https://dev.to/konstantinas\_mamonas/kafka-producers-explained-partitioning-batching-and-reliability-4bm8](https://dev.to/konstantinas_mamonas/kafka-producers-explained-partitioning-batching-and-reliability-4bm8)  
20. Boosting Kafka Throughput with Spring Kafka Batch Listener and Async Processing, accessed January 12, 2026, [https://dev.to/sanjay\_kumar\_senthilvel/boosting-kafka-throughput-with-spring-kafka-batch-listener-and-async-processing-39bi](https://dev.to/sanjay_kumar_senthilvel/boosting-kafka-throughput-with-spring-kafka-batch-listener-and-async-processing-39bi)  
21. Exactly-once Semantics is Possible: Here's How Apache Kafka Does it \- Confluent, accessed January 12, 2026, [https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/)  
22. Understanding DynamoDB Pricing (2025) \- Bytebase, accessed January 12, 2026, [https://www.bytebase.com/blog/understanding-dynamodb-pricing/](https://www.bytebase.com/blog/understanding-dynamodb-pricing/)  
23. DynamoDB or Aurora/RDS? Should we always use DynamoDB? \- DEV Community, accessed January 12, 2026, [https://dev.to/napicella/dynamodb-or-aurora-rds-should-we-always-use-dynamodb-51d5](https://dev.to/napicella/dynamodb-or-aurora-rds-should-we-always-use-dynamodb-51d5)  
24. AWS Prescriptive Guidance \- Mainframe data replication strategy for the AWS Cloud \- AWS Documentation, accessed January 12, 2026, [https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/strategy-mainframe-data-replication/strategy-mainframe-data-replication.pdf](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/strategy-mainframe-data-replication/strategy-mainframe-data-replication.pdf)