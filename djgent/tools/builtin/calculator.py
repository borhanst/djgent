"""Calculator tool for mathematical operations."""

import ast
import operator
from typing import Any, Union

from djgent.tools.base import Tool


class CalculatorTool(Tool):
    """
    Perform mathematical calculations.

    Supports basic arithmetic: +, -, *, /, **, %, and parentheses.
    """

    name = "calculator"
    description = "Perform mathematical calculations. Supports +, -, *, /, **, %, and parentheses."

    # Safe operators
    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval_expr(self, node: ast.AST) -> Union[int, float]:
        """Safely evaluate an AST node."""
        if isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.Constant):  # Python >= 3.8
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type}")
            return self._OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_expr(node.operand)
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op_type}")
            return self._OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Unsupported expression type: {type(node)}")

    def _run(self, expression: str) -> Union[int, float, str]:
        """
        Evaluate a mathematical expression.

        Args:
            expression: The mathematical expression to evaluate

        Returns:
            The result of the calculation
        """
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval_expr(tree.body)
            return result
        except Exception as e:
            return f"Error: {str(e)}"
