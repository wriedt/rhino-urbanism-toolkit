"""Behavior tests for supported naming conventions and ambiguous family splits."""
import unittest
import block_versions as n


def definitions(names):
    return [dict(index=i, id=str(i), name=name, editable=True) for i, name in enumerate(names)]


def targets(plan):
    changes = {r['id']: r['new'] for r in plan['renames']}
    return [changes.get(d['id'], d['name']) for d in plan['members']]


class NamingTests(unittest.TestCase):
    def test_next_formats(self):
        for before, token, after in [('House_v02', 'v02', 'House_v03'),
            ('House_001', '001', 'House_002'), ('House 1', '1', 'House 2'),
            ('House_A', 'A', 'House_B'), ('House_A01', 'A01', 'House_A02'),
            ('House_z', 'z', 'House_aa'), ('House_099', '099', 'House_100'),
            ('House_999', '999', 'House_1000'), ('1', '1', '2'),
            ('House-V02', 'V02', 'House-V03')]:
            with self.subTest(before=before):
                self.assertEqual(n.next_version(definitions([before]), n.describe(before, token)), after)

    def test_highest_including_unused_and_reserved(self):
        ds = definitions(['House_v02', 'House_v09', 'Tree_v30'])
        self.assertEqual(n.next_version(ds, n.describe('House_v02', 'v02')), 'House_v10')
        self.assertEqual(n.next_version(ds, n.describe('House_v02', 'v02'), ['House_v10']), 'House_v11')

    def test_letters_follow_highest_family_version(self):
        ds=definitions(['Part_A','Part_Z'])
        self.assertEqual(n.next_version(ds,n.describe('Part_A','A')),'Part_AA')
        self.assertEqual(n.next_version(ds,n.describe('Part_Z','Z')),'Part_AA')
        ds=definitions(['Part_A','Part_B','Part_D','Part_Z'])
        self.assertEqual(n.next_version(ds,n.describe('Part_A','A')),'Part_AA')
        self.assertEqual(n.next_version(ds,n.describe('Part_A','A'),['Part_AA']),'Part_AB')

    def test_consolidation_examples(self):
        for names, low, expected in [(['01', '02', '04', '06'], False, ['01','02','03','04']),
            (['01', '01 copy', '03'], False, ['01','02','03']),
            (['12', '12 01', '13', '14'], True, ['12','13','14','15']),
            (['12', '12 01', '13', '14'], False, ['01','02','03','04'])]:
            ds = definitions(['House_' + s for s in names])
            spec = n.describe(ds[0]['name'], names[0])
            self.assertEqual(targets(n.consolidation_plan(ds, spec, low)), ['House_' + s for s in expected])

    def test_alphabetic_and_compound_consolidation(self):
        for names, token, low, expected in [(['Part_C', 'Part_F', 'Part_F copy'], 'C', True,
            ['Part_C','Part_D','Part_E']), (['Part_A03','Part_A08'], 'A03', False,
            ['Part_A01','Part_A02'])]:
            self.assertEqual(targets(n.consolidation_plan(definitions(names), n.describe(names[0],token),low)),expected)

    def test_nested_duplicate_order(self):
        ds = definitions(['House_12', 'House_12 01', 'House_12 02', 'House_12 01 copy', 'House_13'])
        plan = n.consolidation_plan(ds,n.describe('House_12','12'),True)
        self.assertEqual([r['old'] for r in plan['renames']],
                         ['House_12 01','House_12 01 copy','House_12 02','House_13'])
        self.assertEqual(targets(plan), ['House_12','House_13','House_14','House_15','House_16'])

    def test_rename_preserves_format_and_duplicates(self):
        for names, token, expected in [(['House_v02','House_v09 copy'],'v02',['Court_v02','Court_v09 copy']),
            (['House_A01','House_A07'],'A01',['Court_A01','Court_A07']),
            (['House_A','House_C'],'A',['Court_A','Court_C']),
            (['House_12','House_12 01','House_13'],'12',['Court_12','Court_12 01','Court_13'])]:
            ds=definitions(names)
            self.assertEqual(targets(n.rename_plan(ds,n.describe(names[0],token),'Court_','')),expected)

    def test_manual_split_and_suffix(self):
        ds=definitions(['Building_02_Left','Building_05_Left','Building_02_Right'])
        spec=n.describe(ds[0]['name'],'02')
        self.assertEqual(targets(n.rename_plan(ds,spec,'Court_','_West')), ['Court_02_West','Court_05_West'])
        self.assertEqual(n.next_version(ds,spec),'Building_06_Left')

    def test_measurement_can_be_left_in_family_name(self):
        ds=definitions(['Tree_Ø10m_v01','Tree_Ø10m_v04','Tree_Ø20m_v01'])
        spec=n.describe(ds[0]['name'],'v01')
        self.assertEqual(n.next_version(ds,spec),'Tree_Ø10m_v05')
        self.assertEqual(len(n.members(ds,spec)),2)
        self.assertEqual(n.next_version(definitions(['House','House_001']),n.describe('House_001','001')),'House_002')

    def test_protection_and_collisions(self):
        ds=definitions(['House_v01','Tree_v01'])
        with self.assertRaises(ValueError):
            n.rename_plan(ds,n.describe('House_v01','v01'),'Tree_','')
        with self.assertRaises(ValueError):
            n.rename_plan(definitions(['House_v01','Tree_v02']),n.describe('House_v01','v01'),'Tree_','')
        ds[0]['editable']=False
        with self.assertRaises(ValueError):
            n.rename_plan(ds,n.describe('House_v01','v01'),'Court_','')
        ds=definitions(['House_03','House_03 copy'])
        before=[d.copy() for d in ds]
        n.consolidation_plan(ds,n.describe('House_03','03'))
        self.assertEqual(ds,before)

    def test_suggestions_do_not_fail_on_plain_names(self):
        for name in ['Tree','TREE','Balcony_3000x1500','2D_TREE_SIMPLE','House_A01']:
            n.suggestions(name,[name])
        self.assertEqual(n.suggestions('Tree',['Tree']),[])
        for name in ['2D_TREE_SIMPLE','Tree_Ø10m','Balcony_3000x1500']:
            self.assertEqual(n.suggestions(name,[name]),[])

    def test_plain_rename(self):
        spec=dict(kind='plain',prefix='Tree',suffix='',marker='',width=0)
        self.assertEqual(targets(n.rename_plan(definitions(['Tree','Tree copy','Trees']),spec,'Oak','')),
                         ['Oak','Oak copy'])

    def test_separator_removal_keeps_version_detection(self):
        for names, token, prefix, expected in [(['House 01','House 03 copy'],'01','Court',
            ['Court01','Court03 copy']), (['House A','House C'],'A','Court',['CourtA','CourtC']),
            (['House v02','House v05'],'v02','Court',['Courtv02','Courtv05'])]:
            plan=n.rename_plan(definitions(names),n.describe(names[0],token),prefix,'')
            self.assertEqual(targets(plan),expected)
            suggestions=n.suggestions(expected[0],expected)
            self.assertEqual(suggestions[0]['token'],token)
            self.assertEqual(len(n.members(definitions(expected),suggestions[0])),2)


if __name__=='__main__':
    unittest.main()
