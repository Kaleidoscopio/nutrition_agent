# nutrition_agent
Support files for an AI Agent in charge of Nutrition and wellfare

Uses:

HTMX        - https://htmx.org/
??? PicoCSS     - https://picocss.com/

##

Requires:

fastapi             - https://fastapi.tiangolo.com/
uvicorn[standard]
jinja2
python-dotenv
bcrypt
python-multipart
itsdangerous

O que eu faria como v1

Food diary - Register daily meals, add/delete/modify foods, calories and quantities. Each item inserted should try to look for a match on the food_master table (using the food_alias for other names). If no match found use id 1 for food (food_master default) and allow use to register calories manually. If user adds food weight/volume calculate calories automatically. 

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

