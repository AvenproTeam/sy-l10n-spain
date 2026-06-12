# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models, tools


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_facturae_tax_info(self):
        """Override to respect the invoice-level tax rounding method.

        In Odoo 18, the base l10n_es_facturae implementation always uses
        ``company_id.tax_calculation_rounding_method`` when computing tax
        amounts for the FacturaE XML.  When the
        ``account_invoice_custom_rounding`` module is installed an invoice can
        carry its own ``tax_calculation_rounding_method`` (e.g. set via the
        partner default or edited manually) that may differ from the company
        setting.  This override replaces the hardcoded company rounding with
        the effective invoice-level rounding so the FacturaE totals match the
        amounts actually posted on the move.
        """
        self.ensure_one()
        # Effective rounding method for *this* invoice (may equal company's).
        invoice_rounding = self.tax_calculation_rounding_method
        company_rounding = self.company_id.tax_calculation_rounding_method

        # When the invoice rounding matches the company rounding the base
        # implementation already does the right thing – no need to duplicate
        # the calculation.
        if not invoice_rounding or invoice_rounding == company_rounding:
            return super()._get_facturae_tax_info()

        # The invoice uses a different rounding method than the company.
        # Re-implement the calculation using the invoice-level method.
        sign = -1 if self.move_type[:3] == "out" else 1
        output_taxes = defaultdict(lambda: {"base": 0, "amount": 0})
        withheld_taxes = defaultdict(lambda: {"base": 0, "amount": 0})
        for line in self.line_ids:
            base = line.balance * sign
            for tax in line.tax_ids:
                tax_amount = base * tax.amount / 100
                if invoice_rounding == "round_per_line":
                    tax_amount = tools.float_round(
                        tax_amount, precision_rounding=self.currency_id.rounding
                    )
                if tools.float_compare(tax.amount, 0, precision_digits=2) >= 0:
                    output_taxes[tax]["base"] += base
                    output_taxes[tax]["amount"] += tax_amount
                else:
                    withheld_taxes[tax]["base"] += base
                    withheld_taxes[tax]["amount"] += tax_amount
        return output_taxes, withheld_taxes
