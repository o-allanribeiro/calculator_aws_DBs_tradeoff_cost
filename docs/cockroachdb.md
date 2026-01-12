# Análise Técnica: CockroachDB

Esta análise foca nas características do CockroachDB, um banco de dados distribuído que se enquadra na categoria NewSQL, avaliando-o para sistemas transacionais de alta vazão.

---

### Modelo Principal

- **Relacional Distribuído (NewSQL), compatível com a API do PostgreSQL.**
O CockroachDB foi projetado do zero para ser um banco de dados relacional distribuído. Ele fala o "dialeto" do PostgreSQL, permitindo que aplicações existentes que usam drivers e ORMs de Postgres (como JDBC, Npgsql, etc.) se conectem a ele, mas com a vantagem de escalar horizontalmente e sobreviver a falhas de nós ou até mesmo de regiões inteiras.

---

### Análise PACELC: `PC/EL`

- **Em caso de Partição (P):** O CockroachDB sempre escolhe **Consistência (C)**. Ele usa o algoritmo de consenso Raft para garantir que as escritas sejam replicadas para um quórum de nós antes de serem confirmadas. Se um quórum não puder ser alcançado devido a uma partição de rede, a transação falhará para garantir a integridade.
- **Em operação Normal (E):** Ele também favorece a **Consistência (C)**, mas busca um balanço com a **Latência (L)**. Todas as transações operam por padrão no nível de isolamento `SERIALIZABLE`, o mais forte possível, o que adiciona latência, mas previne anomalias.

---

### Bônus (Prós)

- **O Melhor de Dois Mundos:** Combina a escalabilidade horizontal e a resiliência de um banco de dados NoSQL com a consistência transacional (ACID) e a poderosa linguagem de consulta (SQL) de um banco de dados relacional.
- **Sobrevivência a Desastres:** A arquitetura é multi-regional e multi-ativa por padrão. Você pode configurar o banco de dados para sobreviver à falha de um nó, de uma zona de disponibilidade ou de uma região inteira, sem perda de dados.
- **Previne "Hot Spots" Nativamente:** Ao contrário do Aurora, o CockroachDB monitora o acesso aos dados e automaticamente divide os "ranges" (pedaços de tabelas) que estão recebendo muita carga e os move para outros nós do cluster. Isso ataca o problema da "Hot Row" na raiz, a nível de infraestrutura.

---

### Ônus (Contras)

- **Latência de Escrita:** O protocolo de consenso Raft exige comunicação entre os nós para confirmar cada escrita, o que inerentemente adiciona latência em comparação com um banco de dados de nó único como o PostgreSQL/Aurora.
- **Complexidade Operacional:** Gerenciar, monitorar e otimizar um cluster distribuído é inerentemente mais complexo do que gerenciar uma única instância de banco de dados ou usar um serviço totalmente serverless como o DynamoDB.
- **Tratamento de Erros de Transação:** Em cenários de alta contenção, transações `SERIALIZABLE` podem falhar e precisar de retentativa. A aplicação (ex: o microsserviço Java) precisa ser construída com uma lógica explícita de "retry" para lidar com esses erros de serialização.

---

### Estrutura de Pesquisa Interna

- **Árvore de Merkle sobre um Armazenamento Chave-Valor (Pebble).**
Internamente, o CockroachDB mapeia todos os dados SQL para um armazenamento chave-valor ordenado (Pebble, que é uma evolução do RocksDB). Ele usa controle de concorrência multi-versão (MVCC) para gerenciar transações, de forma semelhante ao PostgreSQL.

---

### Complexidade e Ecossistema (Java/Kafka)

- **Curva de Aprendizado:** **Média.** A sintaxe SQL e a compatibilidade com drivers de PostgreSQL tornam o início fácil. A complexidade está em entender o comportamento transacional distribuído, como o isolamento `SERIALIZABLE` funciona, e como lidar com os *retries* de transação de forma idempotente.
- **Potenciais Problemas:** Se a lógica de *retry* de transação não for bem implementada na aplicação Java, pode haver erros inesperados sob alta carga. A configuração de topologia e localidade dos dados para otimizar a latência pode ser complexa.
- **Integração com Kafka (MSK):** **Excelente.** Possui um mecanismo de CDC (Change Data Capture) nativo e robusto chamado **Changefeeds**. Um `CHANGEFEED` pode ser criado com uma única instrução SQL para enviar todas as alterações de uma ou mais tabelas diretamente para um tópico Kafka em formato Avro ou JSON, com baixa latência e alta confiabilidade.

---

### Casos de Uso de Tabela Sugeridos

- **Ledger de Eventos:** **Perfeito.** Funciona de forma similar ao Aurora, mas com a vantagem de escalar horizontalmente à medida que o volume de transações cresce.
- **Tabela de Saldos:** **Excelente.** É um dos casos de uso mais fortes. Ele lida com o problema de "Hot Row" de forma muito mais elegante que o Aurora devido ao `range splitting` automático, tornando-o um forte candidato para a tabela principal de saldos, mesmo sob alta contenção.
- **Configuração de Cliente:** **Perfeito.** Sendo um banco de dados relacional, lida com esses dados com facilidade.
- **Tabela de Idempotência:** **Perfeito.** Usa uma `UNIQUE constraint` padrão do SQL, que é distribuída e garantida pelo protocolo de consenso.

---

### Principais Configurações ao Provisionar

- **Número de Nós:** Define a capacidade total (CPU, memória, armazenamento) e a resiliência do cluster. Aumentar o número de nós escala o sistema como um todo.
- **Região/Localidade:** Configurações a nível de nó que definem onde eles estão geograficamente localizados. Isso é crucial para otimizar a latência (colocando dados perto dos usuários) e para garantir a sobrevivência a desastres regionais.
- **Replication Factor:** (Tipicamente 3 ou 5) Define quantas cópias de cada "range" de dados são mantidas no cluster para garantir a resiliência contra falhas de nós.
- **Topologia de Tabelas:** Permite definir a nível de tabela ou linha onde os dados devem residir geograficamente, otimizando a performance para aplicações globais.
