"""
Unit Tests for Standalone BioNER Module
=======================================
Tests for the standalone biomedical NER system using shell scripts.
"""

import pytest
import tempfile
import os
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '/app/NER')

from standalone_bioner import (
    StandaloneBioNER,
    COMMON_ONTOLOGIES,
    get_common_ontology_urls,
    show_common_ontologies
)


class TestStandaloneBioNERInit:
    """Tests for StandaloneBioNER initialization"""
    
    def test_default_initialization(self):
        """Test initialization with default parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            
            ner = StandaloneBioNER(
                data_dir=data_dir,
                scripts_dir=scripts_dir
            )
            
            assert ner.data_dir.exists()
            assert ner.scripts_dir.exists()
            assert ner.metadata_file.exists()
            assert ner.metadata == {}
    
    def test_existing_metadata_loading(self):
        """Test loading existing metadata"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(data_dir)
            
            # Create metadata file
            metadata = {
                'doid': {
                    'url': 'http://example.com/doid.owl',
                    'type': 'owl',
                    'processed_at': '2025-01-01'
                }
            }
            
            metadata_file = os.path.join(data_dir, 'metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
            
            scripts_dir = os.path.join(tmpdir, 'scripts')
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            
            assert 'doid' in ner.metadata
            assert ner.metadata['doid']['url'] == 'http://example.com/doid.owl'


class TestCheckDependencies:
    """Tests for check_dependencies method"""
    
    @patch('shutil.which')
    def test_all_dependencies_present(self, mock_which):
        """Test when all dependencies are available"""
        mock_which.return_value = '/usr/bin/bash'  # All commands found
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            result = ner.check_dependencies()
            
            assert result is True
    
    @patch('shutil.which')
    def test_missing_dependencies(self, mock_which):
        """Test when dependencies are missing"""
        # Simulate missing 'gawk'
        def which_side_effect(cmd):
            return None if cmd == 'gawk' else '/usr/bin/' + cmd
        
        mock_which.side_effect = which_side_effect
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            result = ner.check_dependencies()
            
            assert result is False


class TestCheckScripts:
    """Tests for check_scripts method"""
    
    def test_scripts_present(self):
        """Test when required scripts are present"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            # Create dummy scripts
            for script in ['process_ontology.sh', 'extract_entities.sh']:
                script_path = os.path.join(scripts_dir, script)
                Path(script_path).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            result = ner.check_scripts()
            
            assert result is True
    
    def test_scripts_missing(self):
        """Test when required scripts are missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            result = ner.check_scripts()
            
            assert result is False


class TestDownloadOntology:
    """Tests for download_ontology method"""
    
    @patch('urllib.request.urlopen')
    def test_download_success(self, mock_urlopen):
        """Test successful ontology download"""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b'<owl>test content</owl>'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            result = ner.download_ontology(
                url='http://example.com/test.owl',
                name='test',
                ontology_type='owl'
            )
            
            assert result.exists()
            assert result.name == 'test.owl'
    
    @patch('urllib.request.urlopen')
    def test_download_failure(self, mock_urlopen):
        """Test failed ontology download"""
        mock_urlopen.side_effect = Exception("Network error")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            with pytest.raises(Exception):
                ner.download_ontology(
                    url='http://example.com/test.owl',
                    name='test'
                )
    
    def test_auto_detect_file_type(self):
        """Test automatic file type detection from URL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = b'content'
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                # Test .owl extension
                result = ner.download_ontology(
                    url='http://example.com/test.owl',
                    name='test'
                )
                assert result.suffix == '.owl'
                
                # Test .rdf extension
                result = ner.download_ontology(
                    url='http://example.com/test.rdf',
                    name='test2'
                )
                assert result.suffix == '.rdf'


class TestProcessOntology:
    """Tests for process_ontology method"""
    
    @patch('subprocess.run')
    def test_process_success(self, mock_run):
        """Test successful ontology processing"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Processing complete',
            stderr=''
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            # Create dummy script
            script_path = os.path.join(scripts_dir, 'process_ontology.sh')
            Path(script_path).touch()
            
            # Create dummy ontology file
            onto_file = os.path.join(data_dir, 'test.owl')
            Path(onto_file).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            result = ner.process_ontology(Path(onto_file))
            
            assert result is True
            mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_process_failure(self, mock_run):
        """Test failed ontology processing"""
        from subprocess import CalledProcessError
        
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd='process_ontology.sh',
            output='Error',
            stderr='Processing failed'
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            script_path = os.path.join(scripts_dir, 'process_ontology.sh')
            Path(script_path).touch()
            
            onto_file = os.path.join(data_dir, 'test.owl')
            Path(onto_file).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            result = ner.process_ontology(Path(onto_file))
            
            assert result is False


class TestAddOntology:
    """Tests for add_ontology method"""
    
    @patch.object(StandaloneBioNER, 'check_dependencies')
    @patch.object(StandaloneBioNER, 'check_scripts')
    @patch.object(StandaloneBioNER, 'download_ontology')
    @patch.object(StandaloneBioNER, 'process_ontology')
    def test_add_ontology_success(self, mock_process, mock_download, 
                                  mock_scripts, mock_deps):
        """Test successful ontology addition"""
        # Setup mocks
        mock_deps.return_value = True
        mock_scripts.return_value = True
        mock_download.return_value = Path('/tmp/test.owl')
        mock_process.return_value = True
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            result = ner.add_ontology(
                url='http://example.com/test.owl',
                name='test',
                description='Test ontology'
            )
            
            assert result == 'test'
            assert 'test' in ner.metadata
            assert ner.metadata['test']['description'] == 'Test ontology'
    
    @patch.object(StandaloneBioNER, 'check_dependencies')
    def test_add_ontology_missing_deps(self, mock_deps):
        """Test adding ontology when dependencies are missing"""
        mock_deps.return_value = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            result = ner.add_ontology(
                url='http://example.com/test.owl',
                name='test'
            )
            
            assert result is None
    
    def test_skip_existing_ontology(self):
        """Test skipping existing ontology"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            # Add metadata manually
            ner.metadata['test'] = {
                'url': 'http://example.com/test.owl',
                'processed_at': '2025-01-01'
            }
            ner._save_metadata()
            
            with patch.object(StandaloneBioNER, 'check_dependencies', return_value=True):
                with patch.object(StandaloneBioNER, 'check_scripts', return_value=True):
                    result = ner.add_ontology(
                        url='http://example.com/test.owl',
                        name='test',
                        skip_if_exists=True
                    )
            
            assert result == 'test'


class TestExtractEntities:
    """Tests for extract_entities method"""
    
    @patch('subprocess.run')
    def test_extract_entities_success(self, mock_run):
        """Test successful entity extraction"""
        # Mock successful extraction
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='0\t8\tdiabetes\thttp://purl.obolibrary.org/obo/DOID_9351\n'
                   '13\t23\thypertension\thttp://purl.obolibrary.org/obo/DOID_10763',
            stderr=''
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            # Create script
            script_path = os.path.join(scripts_dir, 'extract_entities.sh')
            Path(script_path).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            
            entities = ner.extract_entities(
                text='diabetes and hypertension',
                lexicon_name='doid'
            )
            
            assert len(entities) == 2
            assert entities[0]['text'] == 'diabetes'
            assert entities[0]['start'] == 0
            assert entities[0]['end'] == 8
            assert 'uri' in entities[0]
    
    @patch('subprocess.run')
    def test_extract_entities_no_results(self, mock_run):
        """Test extraction with no results"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',
            stderr=''
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            script_path = os.path.join(scripts_dir, 'extract_entities.sh')
            Path(script_path).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            
            entities = ner.extract_entities(
                text='random text',
                lexicon_name='doid'
            )
            
            assert entities == []
    
    @patch('subprocess.run')
    def test_extract_entities_script_error(self, mock_run):
        """Test extraction when script fails"""
        from subprocess import CalledProcessError
        
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd='extract_entities.sh',
            stderr='Script error'
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            scripts_dir = os.path.join(tmpdir, 'scripts')
            os.makedirs(data_dir)
            os.makedirs(scripts_dir)
            
            script_path = os.path.join(scripts_dir, 'extract_entities.sh')
            Path(script_path).touch()
            
            ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
            
            entities = ner.extract_entities(
                text='test',
                lexicon_name='doid'
            )
            
            assert entities == []


class TestListOntologies:
    """Tests for list_ontologies and related methods"""
    
    def test_list_ontologies_empty(self):
        """Test listing when no ontologies are loaded"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            result = ner.list_ontologies()
            
            assert result == {}
    
    def test_list_ontologies_with_data(self):
        """Test listing ontologies with metadata"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            ner.metadata = {
                'doid': {
                    'url': 'http://example.com/doid.owl',
                    'type': 'owl',
                    'processed_at': '2025-01-01'
                }
            }
            
            result = ner.list_ontologies()
            
            assert 'doid' in result
            assert result['doid']['url'] == 'http://example.com/doid.owl'
    
    def test_get_ontology_info(self):
        """Test getting specific ontology info"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            ner.metadata = {
                'doid': {
                    'url': 'http://example.com/doid.owl',
                    'description': 'Disease Ontology'
                }
            }
            
            info = ner.get_ontology_info('doid')
            
            assert info is not None
            assert info['description'] == 'Disease Ontology'
    
    def test_get_ontology_info_not_found(self):
        """Test getting info for non-existent ontology"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            info = ner.get_ontology_info('nonexistent')
            
            assert info is None


class TestRemoveOntology:
    """Tests for remove_ontology method"""
    
    def test_remove_ontology_success(self):
        """Test successful ontology removal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            # Add metadata
            ner.metadata['test'] = {
                'url': 'http://example.com/test.owl',
                'type': 'owl'
            }
            ner._save_metadata()
            
            # Create dummy files
            for suffix in ['_word1.txt', '_word2.txt', '_words.txt']:
                file_path = ner.data_dir / f'test{suffix}'
                file_path.touch()
            
            result = ner.remove_ontology('test', delete_source=False)
            
            assert result is True
            assert 'test' not in ner.metadata
    
    def test_remove_ontology_not_found(self):
        """Test removing non-existent ontology"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            result = ner.remove_ontology('nonexistent')
            
            assert result is False


class TestVerifyLexicon:
    """Tests for verify_lexicon method"""
    
    def test_verify_complete_lexicon(self):
        """Test verifying complete lexicon"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            # Create all required files
            required_files = [
                'test_word1.txt',
                'test_word2.txt',
                'test_words.txt',
                'test_words2.txt'
            ]
            
            for filename in required_files:
                file_path = ner.data_dir / filename
                file_path.touch()
            
            result = ner.verify_lexicon('test')
            
            assert result is True
    
    def test_verify_incomplete_lexicon(self):
        """Test verifying incomplete lexicon"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ner = StandaloneBioNER(data_dir=tmpdir, scripts_dir=tmpdir)
            
            # Create only some files
            (ner.data_dir / 'test_word1.txt').touch()
            
            result = ner.verify_lexicon('test')
            
            assert result is False


class TestCommonOntologies:
    """Tests for common ontology utilities"""
    
    def test_common_ontologies_constant(self):
        """Test COMMON_ONTOLOGIES constant"""
        assert 'doid' in COMMON_ONTOLOGIES
        assert 'chebi' in COMMON_ONTOLOGIES
        assert 'hpo' in COMMON_ONTOLOGIES
        assert 'ordo' in COMMON_ONTOLOGIES
        
        # Check structure
        assert 'url' in COMMON_ONTOLOGIES['doid']
        assert 'description' in COMMON_ONTOLOGIES['doid']
    
    def test_get_common_ontology_urls(self):
        """Test get_common_ontology_urls function"""
        urls = get_common_ontology_urls()
        
        assert isinstance(urls, dict)
        assert len(urls) > 0
        assert 'doid' in urls


# Fixtures
@pytest.fixture
def ner_instance():
    """Fixture providing a NER instance"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, 'data')
        scripts_dir = os.path.join(tmpdir, 'scripts')
        
        ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
        yield ner


@pytest.fixture
def temp_ontology_files(tmp_path):
    """Fixture providing temporary ontology files"""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    
    # Create lexicon files
    lexicon_name = 'test'
    files = {
        'word1': data_dir / f'{lexicon_name}_word1.txt',
        'word2': data_dir / f'{lexicon_name}_word2.txt',
        'words': data_dir / f'{lexicon_name}_words.txt',
        'words2': data_dir / f'{lexicon_name}_words2.txt',
        'links': data_dir / f'{lexicon_name}_links.tsv'
    }
    
    for file_path in files.values():
        file_path.touch()
    
    yield data_dir, lexicon_name, files


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])