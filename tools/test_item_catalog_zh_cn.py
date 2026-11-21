import contextlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import build_item_catalog_zh_cn as builder


class TestItemCatalog(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        self.database = self.root / 'items.db'
        self.catalog = self.root / 'zh_CN.json'
        self.catalog.write_text(json.dumps({'item': {'73': '铜剑'}}), encoding='utf-8')
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            for table in builder.TABLES:
                connection.execute(
                    f'CREATE TABLE {table} '
                    '(id TEXT, "基本名稱" TEXT, "物品類別" TEXT, "說明定義" TEXT)'
                )
            connection.executemany('INSERT INTO item VALUES (?, ?, ?, ?)', [
                ('73', 'Copper Sword', '劍', 'This is a test description.'),
                ('80', '</script><script>bad()</script>', '一般', ''),
                ('name', 'Header', 'Header', ''),
            ])
            connection.execute(
                'INSERT INTO item2 VALUES (?, ?, ?, ?)',
                ('73', 'Different later row', '劍', ''),
            )
            connection.commit()

    def test_first_table_wins_like_server_lookup(self):
        rows = builder.read_items(self.database, self.catalog)
        self.assertEqual([row['id'] for row in rows], [73, 80])
        self.assertEqual(rows[0]['en'], 'Copper Sword')
        self.assertEqual(rows[0]['zh'], '铜剑')
        self.assertEqual(rows[0]['table'], 'item')
        self.assertEqual(rows[1]['zh'], '')

    def test_official_chinese_description_takes_precedence(self):
        rows = builder.read_items(
            self.database, self.catalog,
            {'73': '学习技能时赠送的装备，不可交易。'},
        )
        self.assertEqual(rows[0]['description'], '学习技能时赠送的装备，不可交易。')

    def test_placeholder_description_is_hidden(self):
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                'INSERT INTO item VALUES (?, ?, ?, ?)',
                ('195', 'Lucky Stone', '一般', '/c$2%s/c*'),
            )
            connection.commit()
        rows = builder.read_items(self.database, self.catalog)
        item = next(row for row in rows if row['id'] == 195)
        self.assertEqual(item['description'], '')

    def test_embedded_placeholder_is_not_shown(self):
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                'INSERT INTO item VALUES (?, ?, ?, ?)',
                ('197', 'Lucky Bag', '一般', 'Open to get: %s'),
            )
            connection.commit()
        rows = builder.read_items(self.database, self.catalog, {'197': '打开后获得：%s'})
        item = next(row for row in rows if row['id'] == 197)
        self.assertEqual(item['description'], '打开后获得：……')

    def test_client_color_markup_is_removed(self):
        rows = builder.read_items(
            self.database, self.catalog,
            {'73': '/c$2学习技能时赠送的装备/c*，不可交易。'},
        )
        self.assertEqual(rows[0]['description'], '学习技能时赠送的装备，不可交易。')

    def test_non_chinese_client_description_is_not_used(self):
        rows = builder.read_items(
            self.database, self.catalog,
            {
                '73': 'カカオ豆を保存していた樽で作られた丈夫なバレル。',
                '80': 'Open it to get one of the following things randomly: '
                      'Large House, Enchanted-Curare Frog Head, Magic Soap.',
            },
        )
        self.assertEqual(rows[0]['description'], '暂无官方中文说明。')
        self.assertEqual(rows[1]['description'], '')

    def test_common_fallback_description_is_chinese(self):
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                'INSERT INTO item VALUES (?, ?, ?, ?)',
                ('196', 'Lucky Stone', '一般', 'Valid for 30 days from the date of first use.'),
            )
            connection.commit()
        rows = builder.read_items(
            self.database, self.catalog, fallbacks={'Valid for 30 days from the date of first use.': '自首次使用起有效期为30天。'},
        )
        item = next(row for row in rows if row['id'] == 196)
        self.assertEqual(item['description'], '自首次使用起有效期为30天。')

    def test_read_does_not_modify_database(self):
        original = self.database.read_bytes()
        builder.read_items(self.database, self.catalog)
        self.assertEqual(self.database.read_bytes(), original)

    def test_generated_page_escapes_embedded_script(self):
        output = self.root / 'index.html'
        subprocess.run([
            sys.executable, str(pathlib.Path(builder.__file__)),
            '--database', str(self.database), '--catalog', str(self.catalog), '--output', str(output),
            '--no-client',
        ], check=True, capture_output=True)
        page = output.read_text(encoding='utf-8')
        self.assertIn('铜剑', page)
        self.assertIn('服务端名称 / 中文说明', page)
        self.assertNotIn('</script><script>bad()</script>', page)
        self.assertIn('\\u003c/script>', page)
        self.assertNotIn('__ITEM_DATA__', page)
        self.assertNotIn('__GENERATED_AT__', page)

    def test_generated_page_has_sort_and_page_size_controls(self):
        output = self.root / 'index.html'
        subprocess.run([
            sys.executable, str(pathlib.Path(builder.__file__)),
            '--database', str(self.database), '--catalog', str(self.catalog), '--output', str(output),
            '--no-client',
        ], check=True, capture_output=True)
        page = output.read_text(encoding='utf-8')
        self.assertIn('id="sort"', page)
        self.assertIn('data-sort="level"', page)
        self.assertIn('id="level-min"', page)
        self.assertIn('id="page-size"', page)
        self.assertIn('每页可选 20、50、100 或 200 条', page)


if __name__ == '__main__':
    unittest.main()
