# Configuração da Infraestrutura AWS (Aurora e DynamoDB)

Este documento detalha como configurar os recursos de banco de dados da AWS (Amazon Aurora e Amazon DynamoDB) que são simulados na aplicação `app.py`. Usaremos a sintaxe do [Terraform](https://www.terraform.io/) para declarar a infraestrutura como código (IaC).

## 🐘 Amazon Aurora PostgreSQL (I/O Optimized)

O Aurora é um banco de dados relacional e sua configuração envolve um "cluster" (que gerencia o armazenamento) e uma ou mais "instâncias" (que fornecem o poder computacional).

### Explicação da Configuração

- **Cluster (`aws_rds_cluster`):** É o contêiner principal. A decisão mais importante aqui é o `storage_type`. Baseado na simulação, onde cargas de trabalho com alto I/O são comuns, o tipo `aurora-io-optimized` é geralmente a melhor escolha para evitar custos variáveis de I/O, como visto no simulador.
- **Instância (`aws_rds_cluster_instance`):** É a máquina virtual (VM) que executa o banco de dados. O `instance_class` (`db.r7g.2xlarge`) foi escolhido no simulador como um exemplo de uma instância potente da família Graviton (ARM), que oferece boa relação custo-benefício. A escolha da instância correta depende diretamente dos requisitos de `TPS de Pico`.
- **Prevenção de "Hot Row":** A solução para o problema de "Hot Row" (disputa em uma única linha) não está na infraestrutura, mas na **lógica da aplicação**. Estratégias como *batching* (agrupamento de transações) ou o uso de uma tabela de ledger em DynamoDB são padrões de software, não configurações de hardware.

### Código Terraform (Exemplo)

```terraform
# 1. Definição do Cluster Aurora
resource "aws_rds_cluster" "aurora_cluster" {
  cluster_identifier      = "cluster-bancario-prod"
  engine                  = "aurora-postgresql"
  engine_version          = "15.3"
  database_name           = "transacoesdb"
  master_username         = "admin"
  master_password         = "SuaSenhaSeguraAqui" # Use o AWS Secrets Manager em produção
  
  # Mapeamento do Simulador: Escolha entre Standard ("aurora") e I/O Optimized
  # Para cargas financeiras com alto TPS, I/O Optimized é geralmente mais barato.
  storage_type            = "aurora-io-optimized"
  
  skip_final_snapshot     = true # Para fins de teste; em produção, defina como false
  db_subnet_group_name    = "seu_db_subnet_group" # Pré-requisito: Subnet Group deve existir
  vpc_security_group_ids  = ["seu_security_group_id"] # Pré-requisito: Security Group deve existir
}

# 2. Definição da Instância (Writer)
resource "aws_rds_cluster_instance" "writer_instance" {
  cluster_identifier      = aws_rds_cluster.aurora_cluster.id
  instance_class          = "db.r7g.2xlarge" # Mapeamento do Simulador: Instância para suportar a carga de TPS
  engine                  = aws_rds_cluster.aurora_cluster.engine
  engine_version          = aws_rds_cluster.aurora_cluster.engine_version
  publicly_accessible   = false
}
```

---

## ⚡ Amazon DynamoDB (On-Demand)

O DynamoDB é um banco de dados NoSQL (chave-valor e documento) e sua configuração é focada na tabela, no modo de capacidade e, crucialmente, no design da chave de partição.

### Explicação da Configuração

- **Tabela (`aws_dynamodb_table`):** A configuração principal. Usamos `billing_mode = "PAY_PER_REQUEST"` (On-Demand), que corresponde ao modelo de custo do simulador e é ideal para cargas de trabalho com picos imprevisíveis, como uma Black Friday.
- **Chave de Partição (`hash_key`):** Esta é a configuração mais crítica para performance. O DynamoDB distribui dados e tráfego com base no valor da chave de partição.
- **Lógica de "Write Sharding":** A opção "Aplicar Write Sharding" no simulador **não é uma configuração da AWS**. É um **padrão de design da aplicação**. Para evitar uma "Partição Quente" (muitas escritas para o mesmo valor de chave), a aplicação deve adicionar um sufixo aleatório ou sequencial à chave. Por exemplo, em vez de usar `CONTA_123` como chave para um ledger, a aplicação geraria chaves como `CONTA_123_01`, `CONTA_123_02`, etc., distribuindo assim as escritas em várias partições lógicas.
- **Consistência Forte:** A opção "Exigir Consistência Forte" também é definida na aplicação no momento da leitura (ex: no SDK `ConsistentRead: true`), não na infraestrutura.

### Código Terraform (Exemplo)

```terraform
# 1. Definição da Tabela DynamoDB
resource "aws_dynamodb_table" "ledger_table" {
  name           = "LedgerTransacoes"
  billing_mode   = "PAY_PER_REQUEST" # Mapeamento do Simulador: On-Demand para picos
  
  # Mapeamento do Simulador: Chave de Partição
  # A lógica de "Write Sharding" acontece na aplicação, que gera valores variados para este atributo.
  # Ex: "CONTA_123_SHARD_1", "CONTA_123_SHARD_2"
  hash_key       = "PK" 
  
  # Chave de Classificação (Opcional, mas útil para séries temporais)
  range_key      = "SK"

  # Definição dos atributos da chave
  attribute {
    name = "PK" # Partition Key
    type = "S"  # String
  }

  attribute {
    name = "SK" # Sort Key
    type = "S"  # String
  }

  tags = {
    Projeto = "SimuladorBancario"
  }
}
```
