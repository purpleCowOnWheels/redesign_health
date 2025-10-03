import sys
from pathlib import Path

# Add parent directory to path to import entity_fns
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from entity_fns import resolve_entity


class TestResolveEntity:
    """Test suite for resolve_entity function"""

    def test_exact_match_by_email(self):
        """Test that exact email match is found with high confidence"""
        entity = {
            'name': 'John Smith',
            'email': 'john.smith@example.com',
            'phone': '123-456-7890',
            'linkedin_url': 'https://linkedin.com/in/johnsmith',
            'address': '123 Main St'
        }
        
        known_entities = [
            {
                'name': 'John Smith',
                'email': 'john.smith@example.com',
                'phone': '123-456-7890',
                'linkedin_url': 'https://linkedin.com/in/johnsmith',
                'address': '123 Main St'
            }
        ]
        
        result = resolve_entity(entity, known_entities)
        
        assert result['is_new'] == False
        assert result['best_match'] is not None
        assert result['confidence'] > 0.9
        assert len(result['matches']) == 1
    
    def test_no_match_new_entity(self):
        """Test that a new entity with no matches is identified"""
        entity = {
            'name': 'Jane Doe',
            'email': 'jane.doe@example.com',
            'phone': '987-654-3210',
            'linkedin_url': 'https://linkedin.com/in/janedoe',
            'address': '456 Oak Ave'
        }
        
        known_entities = [
            {
                'name': 'John Smith',
                'email': 'john.smith@example.com',
                'phone': '123-456-7890',
                'linkedin_url': 'https://linkedin.com/in/johnsmith',
                'address': '123 Main St'
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.7)
        
        assert result['is_new'] == True
        assert result['best_match'] is None
        assert result['confidence'] == 0.0
        assert len(result['matches']) == 0
    
    def test_partial_match_similar_name(self):
        """Test matching by similar name but different contact info"""
        entity = {
            'name': 'John A. Smith',
            'email': 'jsmith@newcompany.com',
            'phone': '555-555-5555',
            'linkedin_url': None,
            'address': '789 Different St'
        }
        
        known_entities = [
            {
                'name': 'John Smith',
                'email': 'john@oldcompany.com',
                'phone': '111-111-1111',
                'linkedin_url': None,
                'address': '123 Main St'
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.5)
        
        # Should have low confidence since only name is similar
        assert result['confidence'] < 0.7
    
    def test_match_by_phone_number(self):
        """Test matching by phone number with different formatting"""
        entity = {
            'name': 'Bob Johnson',
            'email': 'bob@example.com',
            'phone': '(555) 123-4567',
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Robert Johnson',
                'email': 'robert@company.com',
                'phone': '5551234567',  # Same number, different format
                'linkedin_url': None,
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.0)
        print(result)
        assert result['is_new'] == False
        assert result['best_match'] is not None
        assert 'phone' in result['best_match']['matching_fields']
    
    def test_match_by_linkedin_url(self):
        """Test matching by LinkedIn URL"""
        entity = {
            'name': 'Sarah Williams',
            'email': 'sarah.new@gmail.com',
            'phone': None,
            'linkedin_url': 'https://linkedin.com/in/sarahwilliams',
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Sarah M. Williams',
                'email': 'sarah.old@yahoo.com',
                'phone': None,
                'linkedin_url': 'https://linkedin.com/in/sarahwilliams',
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.5)
        
        assert result['is_new'] == False
        assert result['best_match'] is not None
        assert 'linkedin_url' in result['best_match']['matching_fields']
    
    def test_empty_known_entities_list(self):
        """Test with empty known people list"""
        entity = {
            'name': 'Test entity',
            'email': 'test@example.com',
            'phone': None,
            'linkedin_url': None,
            'address': None
        }
        
        result = resolve_entity(entity, [])
        
        assert result['is_new'] == True
        assert result['best_match'] is None
        assert result['confidence'] == 0.0
        assert len(result['matches']) == 0
    
    def test_multiple_matches_sorted_by_confidence(self):
        """Test that multiple matches are sorted by confidence"""
        entity = {
            'name': 'Mike Davis',
            'email': 'mike@example.com',
            'phone': '555-0000',
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Mike Davis',
                'email': 'mike@example.com',
                'phone': '555-0000',
                'linkedin_url': None,
                'address': None
            },
            {
                'name': 'Michael Davis',
                'email': 'different@example.com',
                'phone': '555-0000',
                'linkedin_url': None,
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.5)
        
        # Should have matches sorted by confidence
        if len(result['matches']) > 1:
            for i in range(len(result['matches']) - 1):
                assert result['matches'][i]['confidence'] >= result['matches'][i + 1]['confidence']
    
    def test_null_and_none_values(self):
        """Test handling of None/null values"""
        entity = {
            'name': 'Test User',
            'email': None,
            'phone': None,
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Test User',
                'email': None,
                'phone': None,
                'linkedin_url': None,
                'address': None
            }
        ]
        
        # Should not crash and should return a result
        result = resolve_entity(entity, known_entities)
        
        assert 'matches' in result
        assert 'best_match' in result
        assert 'is_new' in result
        assert 'confidence' in result
    
    def test_custom_threshold(self):
        """Test custom threshold value"""
        entity = {
            'name': 'Alice Cooper',
            'email': 'alice@example.com',
            'phone': 6106755539,
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Alicia Cooper',
                'email': 'alicia@example.com',
                'phone': 6106755538,
                'linkedin_url': None,
                'address': None
            }
        ]
        
        # With low threshold, should find match
        result_low = resolve_entity(entity, known_entities, threshold=0.05)
        print(result_low)
        assert result_low['is_new'] == False
        
        # With high threshold, might not find match
        result_high = resolve_entity(entity, known_entities, threshold=0.95)
        print(result_high)
        assert result_high['is_new'] == True
    
    def test_different_email_domains_no_match(self):
        """Test that same name but completely different emails don't match"""
        entity = {
            'name': 'John Smith',
            'email': 'john@company-a.com',
            'phone': None,
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'John Smith',
                'email': 'john@company-b.com',
                'phone': None,
                'linkedin_url': None,
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.7)
        
        # Should not match - only name is similar, email is different
        assert result['is_new'] == True
        assert result['confidence'] < 0.1
    
    def test_different_phone_numbers_no_match(self):
        """Test that same name but different phone numbers don't match"""
        entity = {
            'name': 'Sarah Johnson',
            'email': None,
            'phone': '555-1111',
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Sarah Johnson',
                'email': None,
                'phone': '555-9999',
                'linkedin_url': None,
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.7)
        
        # Should not match - phone is highly weighted and is different
        assert result['is_new'] == True
        assert result['confidence'] < 0.15
    
    def test_different_linkedin_urls_no_match(self):
        """Test that different LinkedIn profiles don't match even with similar names"""
        entity = {
            'name': 'Michael Brown',
            'email': None,
            'phone': None,
            'linkedin_url': 'https://linkedin.com/in/michaelbrown123',
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Michael Brown',
                'email': None,
                'phone': None,
                'linkedin_url': 'https://linkedin.com/in/michaelbrown456',
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.7)
        
        # Should not match - LinkedIn URL is highly weighted and is different
        print(result)
        assert result['is_new'] == True

        assert result['confidence'] < 0.75
    
    def test_typo_in_email_no_match(self):
        """Test that typos in email prevent matching"""
        entity = {
            'name': 'Emma Wilson',
            'email': 'emma.wilson@gmail.com',
            'phone': None,
            'linkedin_url': None,
            'address': None
        }
        
        known_entities = [
            {
                'name': 'Emma Wilson',
                'email': 'emma.wilsn@gmail.com',  # Typo: missing 'o'
                'phone': None,
                'linkedin_url': None,
                'address': None
            }
        ]
        
        result = resolve_entity(entity, known_entities, threshold=0.7)
        
        # Should not match - email is different despite phone matching
        assert result['is_new'] == True

    def test_match_by_website(self):
        """Test matching by website URL"""
        entity = {
            'name': 'TechCorp Inc',
            'email': 'contact@techcorp.com',
            'phone': None,
            'linkedin_url': None,
            'website': 'https://www.techcorp.com',
            'address': None
        }

        known_entities = [
            {
                'name': 'TechCorp',
                'email': 'info@techcorp.com',
                'phone': None,
                'linkedin_url': None,
                'website': 'http://techcorp.com',  # Same site, different protocol/www
                'address': None
            }
        ]

        result = resolve_entity(entity, known_entities, threshold=0.5)

        assert result['is_new'] == False
        assert result['best_match'] is not None
        assert 'website' in result['best_match']['matching_fields']
        assert result['best_match']['matching_fields']['website'] == 1.0

    def test_different_websites_no_match(self):
        """Test that different websites don't cause false matches"""
        entity = {
            'name': 'Company A',
            'email': None,
            'phone': None,
            'linkedin_url': None,
            'website': 'https://companya.com',
            'address': None
        }

        known_entities = [
            {
                'name': 'Company A',
                'email': None,
                'phone': None,
                'linkedin_url': None,
                'website': 'https://companyb.com',
                'address': None
            }
        ]

        result = resolve_entity(entity, known_entities, threshold=0.7)

        # Should not match - only name is similar, website is different
        assert result['is_new'] == True
        assert result['confidence'] < 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])