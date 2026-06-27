SELECT 
    m.entry_date,
    m.daily_kcal AS calories_consumed,
    e.tdee_kcal AS calories_burned,
    e.net_balance_kcal AS daily_net,
    b.weight_kg AS current_weight
FROM daily_meal m
LEFT JOIN daily_expenditure e 
    ON m.entry_date = e.entry_date AND m.user_name = e.user_name
LEFT JOIN body_metrics b 
    ON m.entry_date = b.entry_date AND m.user_name = b.user_name
WHERE m.user_name = 'Daniel Almeida'
ORDER BY m.entry_date DESC;