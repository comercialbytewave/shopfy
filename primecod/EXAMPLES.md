# 📚 Exemplos de Uso - Primecod Importer

## 🚀 Execução Básica

### Rodar o pipeline completo
```bash
python main.py all
```

### Rodar etapas individuais
```bash
python main.py capture   # Captura dados da API
python main.py schema    # Gera schema Prisma
python main.py push      # Cria tabelas no PostgreSQL
python main.py import    # Importa dados para o banco
```

## 🔍 Consultando os Dados

### Conectar ao banco PostgreSQL

```bash
# Linux/Mac
psql primecod

# Windows (se instalado)
psql -U postgres primecod
```

### Consultas SQL Úteis

#### 1. Ver todos os produtos

```sql
SELECT id, name, price, cost, stock FROM products LIMIT 10;
```

#### 2. Contar produtos por estoque

```sql
SELECT stock, COUNT(*) as total FROM products GROUP BY stock;
```

#### 3. Produtos mais caros

```sql
SELECT name, price, cost, (price - cost) as profit 
FROM products 
ORDER BY price DESC 
LIMIT 10;
```

#### 4. Produtos com melhor margem de lucro

```sql
SELECT name, price, cost, (price - cost) as profit,
       ROUND((((price - cost) / cost) * 100)::numeric, 2) as margin_percent
FROM products
WHERE cost > 0
ORDER BY (price - cost) DESC
LIMIT 10;
```

#### 5. Categoria com mais produtos

```sql
SELECT category_name, COUNT(*) as total
FROM products
GROUP BY category_name
ORDER BY total DESC
LIMIT 5;
```

#### 6. Produtos com quantidade > 500

```sql
SELECT id, name, quantity, stock
FROM products
WHERE quantity > 500
ORDER BY quantity DESC;
```

#### 7. Buscar produto por nome

```sql
SELECT id, name, price, stock
FROM products
WHERE name ILIKE '%massager%';  -- Case-insensitive search
```

#### 8. Listar todas as categorias únicas

```sql
SELECT DISTINCT category_name
FROM products
WHERE category_name IS NOT NULL
ORDER BY category_name;
```

#### 9. Produtos sem descrição

```sql
SELECT id, name, sku
FROM products
WHERE description IS NULL OR description = '';
```

#### 10. Distribuição de preços

```sql
SELECT 
  CASE 
    WHEN price < 20 THEN '< $20'
    WHEN price < 50 THEN '$20-$50'
    WHEN price < 100 THEN '$50-$100'
    ELSE '> $100'
  END as price_range,
  COUNT(*) as total,
  ROUND(AVG(price)::numeric, 2) as avg_price
FROM products
GROUP BY price_range
ORDER BY total DESC;
```

## 🐍 Usando Python com o Prisma Client

### Instalar e gerar cliente

```bash
pip install prisma
python -m prisma generate --schema prisma/schema.prisma
```

### Consultar dados em Python

```python
import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    
    # Buscar um produto
    product = await db.product.find_first(
        where={"name": {"contains": "massager"}}
    )
    print(product)
    
    # Buscar todos
    products = await db.product.find_many(
        take=10,  # Limit 10
    )
    print(f"Total: {len(products)}")
    
    # Com filtro
    high_price = await db.product.find_many(
        where={"price": {"gt": 50}},
        order_by={"price": "desc"},
    )
    print(f"Produtos > $50: {len(high_price)}")
    
    await db.disconnect()

# Executar
asyncio.run(main())
```

## 📊 Relatórios

### Relatório de estoque

```sql
-- Relatório por nível de estoque
SELECT 
  stock,
  COUNT(*) as quantidade,
  SUM(quantity) as unidades_totais,
  AVG(price) as preco_medio,
  MIN(price) as preco_minimo,
  MAX(price) as preco_maximo
FROM products
GROUP BY stock
ORDER BY quantidade DESC;
```

### Relatório de vendas potenciais

```sql
SELECT 
  category_name,
  COUNT(*) as produtos,
  SUM(quantity) as unidades,
  ROUND(SUM(price * quantity)::numeric, 2) as valor_total_estoque,
  ROUND(AVG(price)::numeric, 2) as preco_medio
FROM products
WHERE quantity > 0
GROUP BY category_name
ORDER BY valor_total_estoque DESC;
```

### Análise de margem por categoria

```sql
SELECT 
  category_name,
  COUNT(*) as produtos,
  ROUND(AVG(price)::numeric, 2) as preco_medio,
  ROUND(AVG(cost)::numeric, 2) as custo_medio,
  ROUND(AVG(price - cost)::numeric, 2) as margem_media,
  ROUND(AVG((price - cost) / cost * 100)::numeric, 2) as percentual_margem
FROM products
WHERE cost > 0 AND price > 0
GROUP BY category_name
ORDER BY percentual_margem DESC;
```

## 🔄 Atualizar Dados

### Atualizar um produto

```bash
python main.py all  # Reimporta tudo automaticamente
```

### Ou fazer em Python

```python
import asyncio
from prisma import Prisma

async def update_product():
    db = Prisma()
    await db.connect()
    
    # Atualizar preço
    updated = await db.product.update(
        where={"id": 1129},
        data={"price": 45.00}
    )
    print(f"Atualizado: {updated.name}")
    
    await db.disconnect()

asyncio.run(update_product())
```

## 📤 Exportar Dados

### Exportar para CSV

```sql
\COPY products(id,name,price,cost,stock,category_name) 
TO '/tmp/products.csv' 
WITH (FORMAT csv, HEADER);
```

### Exportar para JSON

```sql
SELECT json_agg(row_to_json(products.*)) 
FROM products 
LIMIT 100;
```

## 🎯 Casos de Uso Comuns

### 1. Encontrar produtos com margem > 50%

```sql
SELECT id, name, price, cost,
       ROUND(((price - cost) / cost * 100)::numeric, 2) as margin_pct
FROM products
WHERE cost > 0 AND price > 0 
      AND (price - cost) / cost > 0.5
ORDER BY margin_pct DESC;
```

### 2. Produtos de risco (baixo estoque)

```sql
SELECT id, name, quantity, stock, price
FROM products
WHERE quantity < 50 AND stock != 'High'
ORDER BY quantity ASC;
```

### 3. Oportunidades de bundling

```sql
SELECT category_name, COUNT(*) as count, AVG(price) as avg_price
FROM products
GROUP BY category_name
HAVING COUNT(*) > 5
ORDER BY avg_price DESC;
```

### 4. Sincronizar com API novamente

```bash
python main.py capture   # Baixa dados frescos
python main.py schema    # Regenera schema se houver novos campos
python main.py push      # Aplica schema
python main.py import    # Reimporta tudo (upsert evita duplicatas)
```

## 🆘 Troubleshooting

### Erro de conexão PostgreSQL

```bash
# Verificar status do PostgreSQL
sudo service postgresql status

# Reiniciar se necessário
sudo service postgresql restart
```

### Erro "Table already exists"

```bash
# Remover e recriar tudo
python -m prisma migrate reset --schema prisma/schema.prisma
python main.py all
```

### Verificar integridade dos dados

```sql
-- Contar registros
SELECT COUNT(*) FROM products;

-- Encontrar IDs duplicadas
SELECT id, COUNT(*) 
FROM products 
GROUP BY id 
HAVING COUNT(*) > 1;
```

## 📈 Performance Tips

### Criar índice para buscas rápidas

```sql
-- Índice no nome para ILIKE
CREATE INDEX idx_products_name ON products (name);

-- Índice na categoria
CREATE INDEX idx_products_category ON products (category_name);

-- Índice no stock
CREATE INDEX idx_products_stock ON products (stock);
```

### Consultas otimizadas

```sql
-- Usar EXPLAIN ANALYZE para debug
EXPLAIN ANALYZE
SELECT name, price FROM products 
WHERE stock = 'High' 
LIMIT 10;
```

## 🎓 Próximos Passos

1. **Criar API** - Usar os dados do Primecod em sua própria API
2. **Dashboard** - Visualizar dados em um dashboard
3. **Alertas** - Configurar alertas para estoque baixo
4. **Automação** - Agendar sincronização via cron job
5. **Relatórios** - Exportar relatórios regulares

---

**Mais dúvidas?** Consulte o [README.md](README.md) ou [STRUCTURE.md](STRUCTURE.md)
