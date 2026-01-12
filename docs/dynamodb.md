# Análise Técnica: Amazon DynamoDB

Esta análise foca nas características do Amazon DynamoDB, o banco de dados NoSQL chave-valor e de documentos da AWS, avaliando-o para sistemas transacionais de alta vazão.

---

### Modelo Principal

- **NoSQL Chave-Valor e Documento.**
O DynamoDB armazena dados em tabelas, que são coleções de itens (semelhante a linhas). Cada item é composto por atributos (semelhante a colunas). O modelo é "schemaless", exceto pela chave primária, que deve ser definida na criação da tabela.

---

### Análise PACELC: `PA/EL`

- **Em caso de Partição (P):** O DynamoDB escolhe **Disponibilidade (A)** em vez de Consistência (C). Em um evento de partição de rede, o DynamoDB se esforçará para permanecer disponível para leituras e escritas, mesmo que isso signifique que algumas leituras possam retornar dados obsoletos (consistência eventual).
- **Em operação Normal (E):** Ele oferece um balanço, mas tende a favorecer a baixa **Latência (L)** em vez da **Consistência (C)** forte. A consistência eventual é o padrão de leitura mais barato e rápido. Leituras fortemente consistentes são uma opção que dobra o custo e aumenta a latência.

---

### Bônus (Prós)

- **Escalabilidade de Escrita "Infinita":** Com o uso correto de chaves de partição e a aplicação de padrões como "Write Sharding", a capacidade de escrita escala horizontalmente de forma quase ilimitada.
- **Latência Previsível:** Oferece performance consistente de milissegundos de um dígito, independentemente do volume de dados armazenado, desde que os padrões de acesso sigam a modelagem da chave.
- **Modelo Serverless:** Elimina completamente a necessidade de gerenciar instâncias, patches, sistemas operacionais ou se preocupar com o dimensionamento do armazenamento.

---

### Ônus (Contras)

- **Complexidade de Modelagem:** Exige uma mudança de mentalidade. O design da tabela (frequentemente "Single Table Design") deve ser feito com base nos padrões de acesso da aplicação, que precisam ser conhecidos previamente.
- **Transações Limitadas:** Embora existam transações ACID (`TransactWriteItems` e `TransactGetItems`), elas são mais limitadas em escopo (até 100 itens) e mais custosas do que as transações nativas em bancos SQL.
- **Flexibilidade de Consulta Reduzida:** As consultas são altamente eficientes, mas limitadas às chaves primárias e índices secundários definidos. Análises complexas ou consultas ad-hoc exigem a exportação dos dados para outros serviços (ex: S3 + Athena).

---

### Estrutura de Pesquisa Interna

- **Hashing na Chave de Partição:** O DynamoDB usa uma função de hash na chave de partição para determinar em qual armazenamento físico o item será gravado. Isso garante uma distribuição uniforme dos dados, que é a base da sua escalabilidade. Para itens com chave de ordenação, eles são armazenados em ordem dentro da mesma partição, de forma similar a uma B-Tree.

---

### Complexidade e Ecossistema (Java/Kafka)

- **Curva de Aprendizado:** **Alta.** A principal dificuldade não está no uso do SDK, mas na mudança de paradigma para a modelagem de dados NoSQL. Um erro no design da chave primária pode ser desastroso para a performance e difícil de corrigir. O AWS SDK for Java 2 é bem documentado e robusto.
- **Potenciais Problemas:** Escolher uma chave de partição de baixa cardinalidade leva a "hot partitions" e throttling. O custo pode escalar rapidamente se leituras consistentes ou transações forem usadas indiscriminadamente.
- **Integração com Kafka (MSK):** **Padrão nativo e poderoso.** Ativar o **DynamoDB Streams** em uma tabela cria um feed de todas as alterações (CDC). Esse stream pode ser conectado a uma função AWS Lambda, que então processa os eventos e os publica em um tópico do Amazon MSK. Essa arquitetura é serverless, robusta e garante a ordem dos eventos por partição.

---

### Casos de Uso de Tabela Sugeridos

- **Ledger de Eventos:** **Bom.** Pode ser modelado usando `conta_id` como Chave de Partição e um `timestamp_transacao_id` composto como Chave de Ordenação. Isso permite consultar todas as transações de uma conta de forma ordenada e eficiente.
- **Tabela de Saldos:** **Ideal para 'Hot Balances'.** É o seu melhor caso de uso em cenários de alta concorrência. A aplicação deve usar "Write Sharding" (ex: `conta_id#shard_N`) como chave de partição para distribuir a carga de escrita, e usar `UpdateItem` com `ConditionExpression` para atualizações atômicas.
- **Configuração de Cliente:** **Bom.** Um cliente e todas as suas configurações podem ser armazenados como um único item (documento JSON), permitindo a leitura de todo o perfil do cliente com uma única e rápida operação `GetItem`.
- **Tabela de Idempotência:** **Perfeito.** Usar uma `ConditionExpression` com `attribute_not_exists()` na chave de idempotência ao chamar `PutItem` é a forma nativa, serverless e altamente performática de garantir que uma operação só seja registrada uma vez.

---

### Principais Configurações ao Provisionar

- **Billing Mode:** A escolha entre `PAY_PER_REQUEST` (On-Demand) e `PROVISIONED`. On-Demand é ideal para cargas de trabalho novas ou imprevisíveis. Provisionado é mais barato para cargas de trabalho estáveis e previsíveis.
- **Partition Key (e Sort Key):** A escolha do atributo para a chave de partição é a decisão de design mais crítica. Ela deve ter alta cardinalidade para distribuir os dados uniformemente. A chave de ordenação (opcional) define a ordem dos itens dentro de uma partição.
- **RCU/WCU (Read/Write Capacity Units):** No modo `PROVISIONED`, define explicitamente quantas leituras/escritas por segundo você está pagando. O auto-scaling pode ser ativado para ajustar esses valores.
- **Global Tables:** Para replicação multi-regional e multi-ativa, provendo baixa latência para usuários globais e alta resiliência a desastres regionais.
