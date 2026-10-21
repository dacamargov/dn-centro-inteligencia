# Evidencia de ejecución — Genie (consulta en lenguaje natural)

> Prerrequisito: **Genie Agent — make it queryable in natural language**
> Sala de Genie **real** sobre el esquema gobernado, consultada vía la Genie
> Conversation API. El app la tiene cableada por `genie_space_id`.

```
space_id : 01f1ade64422109f89b4df24b4eb6f15
title    : dichter & neira · Centro de Inteligencia
desc     : Exploración en lenguaje natural de la medición de ejecución en punto
           de venta de Nestlé en Latinoamérica. Datos sintéticos.
```

Cada bloque es una corrida real: pregunta en español → SQL que **generó Genie**
sobre las tablas de Unity Catalog → respuesta con los números reales. Los
`conversation_id` quedan registrados.

---

## P1 · "¿Cuáles son las 5 tiendas con peor disponibilidad promedio?"
`status: COMPLETED` · `conversation_id: 01f1cd56d454116bba2971d9cb06a36c` · `total_row_count: 5`

**SQL generado por Genie:**
```sql
WITH disponibilidad_tienda AS (
  SELECT v.store_id, t.nombre AS tienda, t.cadena, t.ciudad, v.country_code,
         ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1) AS disponibilidad_pct,
         COUNT(*) AS observaciones
  FROM dacamargovws_catalog.ditcher.visitas v
  INNER JOIN dacamargovws_catalog.ditcher.tiendas t ON v.store_id = t.store_id
  WHERE v.es_cliente = true
    AND v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
    AND t.nombre IS NOT NULL
  GROUP BY v.store_id, t.nombre, t.cadena, t.ciudad, v.country_code
), ranking AS (
  SELECT *, RANK() OVER (ORDER BY disponibilidad_pct ASC) AS rnk
  FROM disponibilidad_tienda
)
SELECT tienda, cadena, ciudad, country_code, disponibilidad_pct, observaciones
FROM ranking WHERE rnk <= 5
ORDER BY disponibilidad_pct ASC, tienda ASC
```

**Respuesta (números reales):**
- Tienda de barrio Bogotá #111 (Bogotá, CO) — **60.0%**, 10 obs
- Tienda Quito #122 (Quito, EC) — **62.5%**, 8 obs
- Bodega Trujillo #138 (Trujillo, PE) — **66.7%**, 12 obs
- Pulpería San José #38 (San José, CR) — **66.7%**, 6 obs
- Automercado San José #29 (San José, CR) — **70.0%**, 10 obs

---

## P2 · "¿Qué categoría tiene el mayor riesgo de quiebre según el modelo?"
`status: COMPLETED` · `conversation_id: 01f1cd56e13111ffad056a907836b2ac` · `total_row_count: 1`

**SQL generado por Genie:**
```sql
WITH quiebres_por_categoria AS (
  SELECT categoria, COUNT(*) AS quiebres
  FROM dacamargovws_catalog.ditcher.visitas
  WHERE visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
    AND es_cliente = true AND en_stock = false AND categoria IS NOT NULL
  GROUP BY categoria
), ranking AS (
  SELECT categoria, quiebres, RANK() OVER (ORDER BY quiebres DESC) AS rank_quiebre
  FROM quiebres_por_categoria
)
SELECT categoria, quiebres FROM ranking WHERE rank_quiebre = 1
ORDER BY quiebres DESC, categoria ASC
```

**Respuesta:** La categoría con mayor riesgo de quiebre es **Culinarios**, con
**45** quiebres de stock.

> Coincide con el modelo de ML (`02_ml.md`), donde Culinarios domina el top-10 de
> riesgo — la señal es consistente entre Genie, el modelo y los agentes.

---

## P3 · "¿Cuál es el share of shelf promedio del cliente por país?"
`status: COMPLETED` · `conversation_id: 01f1cd56ede313bd86144f5ebc401710` · `total_row_count: 10`

**SQL generado por Genie:**
```sql
SELECT p.pais,
       ROUND(try_divide(100.0 * SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END),
                        NULLIF(SUM(v.facings), 0)), 1) AS share_of_shelf_pct
FROM dacamargovws_catalog.ditcher.visitas v
JOIN dacamargovws_catalog.ditcher.paises p ON v.country_code = p.country_code
WHERE v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES AND p.pais IS NOT NULL
GROUP BY p.pais
ORDER BY share_of_shelf_pct DESC
```

**Respuesta (números reales):** el share of shelf del cliente va de **27.1%** a
**30.1%** en 10 países. Guatemala lidera (30.1%); Colombia y Perú son los más
bajos (27.1%).

---

## Por qué satisface el requisito

- La sala es **real** (no respuestas precargadas) y traduce preguntas en español a
  SQL ejecutable sobre las tablas gobernadas de Unity Catalog.
- Aprovecha las PK/FK y los comentarios declarados en `03_unity_catalog.md` para
  resolver joins (`visitas`↔`tiendas`↔`paises`) correctamente.
- El app expone esta sala a negocio por `genie_space_id`.
