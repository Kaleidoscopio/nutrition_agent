---
name: energy-balance-analytics
description: Retrieve historical dietary data, calculate average caloric intake, and generate future weight projections based on the user's energy balance.
---

# Skill: Health Analytics and Weight Projections

## When to Use
- Use this skill when the user asks for historical metric averages (e.g., "What was my average calorie intake this week?", "How many calories did I eat on average this month?").
- Use this skill when the user asks for weight forecasts or projections (e.g., "What will my weight be in 10 days / 1 month / 3 months if I maintain this deficit?").

## Core Capabilities & Tool Definitions
The LLM should invoke the following tool representations when the user requests analytical insights. ALWAYS include the `user_name` parameter based on the current user context.

### 1. `get_average_calories`
Calculates the mean daily calorie intake over a specified trailing window.
- **Parameters:**
  - `days` (integer, required): The number of days to look back (e.g., `7` for weekly average, `30` for monthly average).
  - `user_name` (string, required): The full name of the user requesting the data (e.g., "Daniel Almeida").

### 2. `predict_weight_change`
Projects future weight modifications using thermodynamic energy balance principles (assuming ~7700 kcal deficit/surplus equals 1 kg of body weight variation) calculated over recent history trendlines.
- **Parameters:**
  - `projection_days` (integer, required): The number of days into the future to project the user's weight (e.g., `10`, `30`, `90`).
  - `user_name` (string, required): The full name of the user requesting the data (e.g., "Daniel Almeida").

## System Instructions & Output Generation
When you receive the structured JSON/tool output from these functions, synthesize the numerical data into a natural, empathetic, and encouraging response in the user's preferred language. 

### Response Guidelines:
- Highlight the current trend (e.g., if they are in a sustainable deficit or surplus).
- Present the projection clearly, mapping out the current weight vs. the forecasted target weight.
- If data is insufficient (status: "error"), gracefully explain what metrics are missing (e.g., missing food records or lack of tracking logs in the local storage/database) and encourage the user to log their meals and weight consistently.