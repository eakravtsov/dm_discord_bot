import logging

# Import the individual tool functions from the new 'tools' directory
from tools.dice_roller import roll_dice
from tools.character_sheet_manager import get_character_sheet

class ToolHandler:
    """
    Imports and prepares individual tool functions for the LLM.
    This class acts as a central registry for all available tools.
    """
    def __init__(self, db_handler):
        """
        Initializes the ToolHandler, preparing tool functions for use.
        Tools that require access to other handlers (like the database)
        are wrapped here to provide that context.
        """
        self.db_handler = db_handler

        # A mapping of tool names to their corresponding, imported functions.
        self.tools = {
            "roll_dice": roll_dice,
            # We need to provide the db_handler to the get_character_sheet function.
            # A lambda function is a concise way to wrap our async function and
            # pass in the necessary db_handler dependency.
            "get_character_sheet": lambda character_name: get_character_sheet(
                character_name=character_name,
                db_handler=self.db_handler
            ),
        }
        logging.info("ToolHandler initialized and has registered all tool functions.")

