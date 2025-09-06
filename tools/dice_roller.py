import random
import logging
import re

def roll_dice(dice_expression):
    """
    Rolls dice based on a standard D&D expression (e.g., '1d20+5').
    Handles multiple dice, single dice, and modifiers.
    Returns the result as a dictionary.
    """
    logging.info(f"Executing tool: roll_dice with expression '{dice_expression}'")
    try:
        # Regex to parse expressions like '2d6', 'd20', '1d20+5', '3d8-2'
        match = re.match(r'(\d*)d(\d+)([+-]\d+)?', dice_expression.lower().strip())
        if not match:
            raise ValueError("Invalid dice format")

        num_dice_str, die_type_str, modifier_str = match.groups()

        num_dice = int(num_dice_str) if num_dice_str else 1
        die_type = int(die_type_str)
        modifier = int(modifier_str) if modifier_str else 0

        rolls = [random.randint(1, die_type) for _ in range(num_dice)]
        total = sum(rolls) + modifier

        logging.info(f"Rolled {dice_expression}: {rolls} + {modifier} = {total}")
        return {"status": "success", "total": total, "rolls": rolls, "modifier": modifier}
    except Exception as e:
        logging.error(f"Error rolling dice for expression '{dice_expression}'", exc_info=e)
        return {"status": "error", "message": "Invalid dice expression. Please use a format like '1d20+5' or '2d6'."}
