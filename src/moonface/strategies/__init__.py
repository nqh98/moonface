"""Strategy plugin API, registry, and reference implementations. Moved out
of signal/ at G5 -- see design spec section 3. strategy_api.py is the
single documented import surface for a strategy module (though, per this
plan's own audit, none of the four reference implementations currently
import it -- each imports moonface.core/moonface.models.evaluate directly;
kept as the intended facade for future strategy authors regardless)."""
