# Análise Técnica: Apache Cassandra e ScyllaDB

Esta análise foca nas características do Apache Cassandra e seu reimplemento em C++, ScyllaDB. Ambos são bancos de dados NoSQL do tipo "wide-column" (colunar), projetados para altíssima disponibilidade e escalabilidade massiva de escrita.

---

### Modelo Principal

- **NoSQL Colunar (Wide-Column).**
Diferente de um modelo chave-valor simples, uma chave em Cassandra/ScyllaDB aponta para um mapa ordenado de colunas. Isso permite modelagens de dados mais ricas, como séries temporais ou entidades com um número variável e grande de atributos. ScyllaDB é um "drop-in replacement" para o Cassandra, compatível com a mesma API e modelo de dados, mas escrito em C++ para performance otimizada, evitando as pausas de *Garbage Collection* da JVM do Cassandra.

---

### Análise PACELC: `PA/EL`

- **Em caso de Partição (P):** O sistema escolhe inequivocamente a **Disponibilidade (A)** sobre a Consistência (C). Ele foi projetado para continuar aceitando leituras e escritas mesmo que os nós não consigam se comunicar entre si, correndo o risco de inconsistência de dados que é resolvida posteriormente por um processo de "reparo".
- **Em operação Normal (E):** Ele favorece a baixa **Latência (L)** sobre a **Consistência (C)**. A consistência é altamente tunável *por operação*. O cliente (a aplicação) decide para cada leitura ou escrita qual o nível de consistência desejado (`ONE`, `QUORUM`, `ALL`), fazendo um trade-off explícito entre performance e garantia de dados.

---

### Bônus (Prós)

- **Performance de Escrita Extrema:** A arquitetura interna, baseada em Log-Structured Merge-Trees (LSM-Trees), é otimizada para altíssimas taxas de ingestão de dados, pois as escritas são apenas um "append" rápido em memória (`memtable`) e em um log sequencial (`commitlog`).
- **Escalabilidade Linear:** A capacidade do cluster escala de forma previsível ao adicionar mais nós. Se você dobrar o número de nós, você dobra a capacidade de armazenamento e de throughput.
- **Alta Disponibilidade:** A arquitetura é "masterless" (sem mestre). Todos os nós são iguais, eliminando pontos únicos de falha.

---

### Ônus (Contras)

- **Consistência Eventual como Padrão:** O padrão é a consistência eventual. Garantir consistência forte (`QUORUM` ou `ALL`) a cada operação aumenta a latência, a complexidade e a chance de falhas se um nó estiver indisponível.
- **Falta de Transações ACID:** Não há suporte para transações multi-partição ou multi-tabela. Isso é uma limitação severa para casos de uso financeiros que exigem a atualização atômica de múltiplos saldos.
- **Leituras Potencialmente Lentas:** Leituras podem ser mais lentas e com latência variável, pois podem exigir a consulta a múltiplos nós, a leitura de múltiplos arquivos em disco (SSTables) e a reconciliação de dados de diferentes versões.

---

### Estrutura de Pesquisa Interna

- **Log-Structured Merge-Tree (LSM-Tree):** O design é otimizado para escritas. Novas escritas e atualizações são inseridas em uma estrutura em memória (`memtable`) e em um log no disco. Quando a `memtable` está cheia, ela é "despejada" para o disco em um arquivo imutável chamado `SSTable`. As leituras precisam consultar a `memtable` e potencialmente múltiplos `SSTables`, que são periodicamente fundidos em um processo de "compactação" para otimizar o acesso.

---

### Complexidade e Ecossistema (Java/Kafka)

- **Curva de Aprendizado:** **Muito Alta.** O modelo de dados colunar, a consistência tunável, a modelagem de dados orientada a consultas, e a necessidade de entender os detalhes operacionais (compactação, reparos, "tombstones") tornam a curva de aprendizado íngreme. O driver Java da DataStax é excelente, mas reflete essa complexidade.
- **Potenciais Problemas:** O manejo incorreto de deleções gera "tombstones" (marcadores de deleção) que não são removidos imediatamente e podem degradar drasticamente a performance de leitura. Uma modelagem de dados ruim pode levar a partições muito grandes ("wide partitions") que se tornam um gargalo.
- **Integração com Kafka (MSK):** Geralmente requer uma implementação do padrão **Transactional Outbox** pela aplicação, de forma similar ao Aurora, para garantir a entrega de eventos. Algumas ferramentas de CDC de terceiros e conectores Kafka existem, mas a integração não é tão nativa ou trivial quanto em outros bancos.

---

### Casos de Uso de Tabela Sugeridos

- **Ledger de Eventos:** **Excelente.** Este é o caso de uso ideal. Perfeito para registrar eventos imutáveis (logs de transações, cliques, eventos de IoT) em altíssima velocidade, onde cada evento é um novo registro e não uma atualização.
- **Tabela de Saldos:** **Não Recomendado.** A falta de transações ACID torna a simples operação de "ler o saldo, subtrair o valor e salvar o novo saldo" inerentemente insegura sob concorrência. Exigiria a implementação de bloqueios distribuídos na camada de aplicação (usando Zookeeper, etc.), o que anula os benefícios de performance do banco.
- **Configuração de Cliente:** **Usável.** Funciona, mas a rigidez das consultas (você só pode consultar pela chave de partição e, opcionalmente, pelas chaves de clustering) pode ser um grande problema a longo prazo se novos padrões de acesso surgirem.
- **Tabela de Idempotência:** **Usável, com ressalvas.** É possível usar "Lightweight Transactions" (LWT) com a sintaxe `IF NOT EXISTS`. No entanto, esta operação é significativamente mais lenta que uma escrita normal, pois exige um round-trip de consenso (Paxos) entre os nós, e deve ser usada com moderação.

---

### Principais Configurações ao Provisionar

- **Replication Factor:** (ex: 3) Define em quantos nós cada pedaço de dado é replicado. É a configuração fundamental para garantir a disponibilidade e durabilidade dos dados.
- **Consistency Level:** (ex: `ONE`, `QUORUM`, `ALL`) Embora não seja uma configuração de provisionamento, é a configuração mais crítica, **definida por operação na aplicação Java**. Ela dita o trade-off entre consistência e latência para cada leitura ou escrita.
- **Compaction Strategy:** (ex: `SizeTieredCompactionStrategy`, `LeveledCompactionStrategy`) Define como os `SSTables` são organizados e mesclados em disco. A escolha tem um impacto profundo na performance de leitura vs. escrita e no uso de espaço em disco.
- **Partitioner:** (ex: `Murmur3Partitioner`) Define o algoritmo de hash usado para distribuir os dados entre os nós do cluster.
