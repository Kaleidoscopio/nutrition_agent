# nutrition_agent
Support files for an AI Agent in charge of Nutrition and wellfare


O que eu faria como v1

Com este schema, a primeira versão da app podia focar-se em 4 ecrãs:

    Dashboard diário — calorias ingeridas, TDEE, balanço líquido, peso do dia;

    Diário alimentar — refeições do dia, adicionar alimento, editar quantidades/macros;

    Peso e métricas — peso, BMI, massa muscular e gordura corporal por dia;

    Alimentos — pesquisa em food_master e aliases para entrada rápida.

Isto aproveita muito bem a base histórica que já tens e evita mexer já na estrutura.
Observações práticas

Há duas coisas que eu afinaria desde já no desenho da app:

    o campo unit em daily_meal_detail vai precisar de regras claras, porque o catálogo está por 100g mas o registo pode ser em gramas, unidades ou porções;

    daily_kcal em daily_meal pode ser tratado como valor persistido ou recalculado da soma do detalhe, e convém escolher uma abordagem para evitar inconsistências.

Como base pragmática, eu tenderia a recalcular os totais a partir de daily_meal_detail sempre que editas refeições, e gravar daily_kcal só como cache/denormalização.
Próximo passo

O melhor próximo passo agora é eu transformar este schema num plano de app concreto, com:

    páginas/endpoints,

    queries principais,

    e ordem de implementação.

Se quiseres, avanço já para isso e proponho a estrutura da v1 em FastAPI + SQLite + HTMX por cima desta base.