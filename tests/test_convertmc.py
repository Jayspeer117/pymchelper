import unittest
from pymchelper import bdo2txt


class TestRunMethod(unittest.TestCase):
    def test_help(self):
        try:
            bdo2txt.main(["--help"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)

    def test_version(self):
        try:
            bdo2txt.main(["--version"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)

    def test_noopt(self):
        try:
            bdo2txt.main([])
        except SystemExit as e:
            self.assertNotEqual(e.code, 0)

    def test_wrongopt(self):
        # TODO enable later
        # try:
        #     bdo2txt.main(["qwerty"])
        # except SystemExit as e:
        #     self.assertNotEqual(e.code, 0)
        pass


if __name__ == '__main__':
    unittest.main()
