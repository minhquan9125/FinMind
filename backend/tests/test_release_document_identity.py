import unittest,uuid
from src.documents.release_identity import release_document_id,validate_document_binding
from src.documents.chunk_reconstruction import ReconstructionError
class IdentityTests(unittest.TestCase):
    index='2264bbb9-024c-5634-abb5-58f399801b34'
    source='0be7ae10-6a32-5b37-9247-db09708bfe11'
    def loc(self):return {'reconstruction':{'document_id':self.source}}
    def test_direct_source_supported(self):
        self.assertEqual(validate_document_binding(self.source,self.index,self.loc())['mode'],'DIRECT_SOURCE_ID')
    def test_release_alias_supported(self):
        alias=release_document_id(self.index,self.source)
        self.assertEqual(alias,'33e0c173-d147-5324-85b5-61e09615e89e')
        self.assertEqual(validate_document_binding(alias,self.index,self.loc())['source_document_id'],self.source)
    def test_other_index_cannot_authorize_alias(self):
        with self.assertRaises(ReconstructionError):validate_document_binding(release_document_id(self.index,self.source),str(uuid.uuid4()),self.loc())
    def test_other_source_cannot_authorize_alias(self):
        loc={'reconstruction':{'document_id':str(uuid.uuid4())}}
        with self.assertRaises(ReconstructionError):validate_document_binding(release_document_id(self.index,self.source),self.index,loc)
    def test_arbitrary_document_rejected(self):
        with self.assertRaises(ReconstructionError):validate_document_binding(str(uuid.uuid4()),self.index,self.loc())
    def test_missing_identity_rejected(self):
        with self.assertRaises(ReconstructionError):validate_document_binding(self.source,self.index,{})
if __name__=='__main__':unittest.main()
