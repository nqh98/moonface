import unittest

from tools.matrix.matrix_evaluate import main


class TestMatrixEvaluateCli(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_missing_required_args_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
