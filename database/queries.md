
# Neo4j Queries

## Apagar todos os nós e relações
MATCH (n) DETACH DELETE n;

## Contar o número total de anos
MATCH (y:Year) RETURN count(y) AS total_years;

## Listar todos os anos em ordem crescente
MATCH (y:Year) RETURN y.year AS year ORDER BY y.year;

## Contar o número total de nós do tipo Drug
MATCH (d:Drug) RETURN count(d);

## Listar todos os nós do tipo Drug
MATCH (d:Drug) RETURN d;

## Contar o número total de empresas
MATCH (c:Company) RETURN count(c) AS total_companies;

## Listar todas as empresas ordenadas pelo nome
MATCH (c:Company) RETURN c.name AS company_name ORDER BY c.name;

## Contar o número total de rotas de administração
MATCH (r:AdminRoute) RETURN count(r) AS total_admin_routes;

## Listar todas as rotas de administração ordenadas pelo nome
MATCH (r:AdminRoute) RETURN r.name AS route_name ORDER BY r.name;
