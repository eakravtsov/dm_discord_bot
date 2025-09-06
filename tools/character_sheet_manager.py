import logging
import asyncio

async def get_character_sheet(character_name, db_handler):
    """
    Fetches a character sheet from Firestore.
    This function is async and requires a db_handler to be passed in.
    Returns the character sheet as a dictionary or an error message.
    """
    logging.info(f"Executing tool: get_character_sheet for '{character_name}'")
    sheet = await db_handler.get_character_sheet(character_name)
    if sheet:
        return {"status": "success", "character_sheet": sheet}
    else:
        return {"status": "error", "message": f"Character sheet for '{character_name}' not found."}
