# request the raw text of The Great Gatsby
import requests
import re

r = requests.get(r'https://www.gutenberg.org/cache/epub/64317/pg64317.txt')
book_content = r.text
    
# you can also subset for the book text
# (removing the project gutenburg introduction/footnotes)
book_content = book_content[1433:277912]

# print(great_gatsby)
# processed_content_1 = great_gatsby.replace('\n\n', '@@PARAGRAPH_BREAK@@') # Temporarily mark real breaks
# processed_content_1 = processed_content_1.replace('\n', ' ') # Replace all other newlines with a space
# processed_content_1 = processed_content_1.replace('@@PARAGRAPH_BREAK@@', '\n\n').strip() # Restore real breaks and clean up
# print("--- Approach 1 ---")
# print(processed_content_1)



# Pattern to find a newline that is NOT followed by a blank line or a sentence-starting character.
# This assumes sentence-ending punctuation followed by a space or newline.
# And also assumes new paragraphs often start with a capital letter or a quote.

# A more sophisticated pattern:
# We want to replace newlines that are:
# 1. NOT followed by another newline (i.e., not a blank line)
# 2. NOT preceded by a sentence-ending punctuation (.?!) and potentially a space.
# 3. NOT followed by a capital letter (start of a new sentence/paragraph)
# 4. NOT followed by a quotation mark (start of dialogue)

# Let's try to replace a newline with a space if it's NOT followed by:
#  - two or more newlines (\n{2,})
#  - a capital letter [A-Z] (assuming new sentences start with capitals)
#  - a quotation mark (["'])
#  - an open parenthesis/bracket ([({])
#  - a dash followed by a space (- ) often for lists or dialogue
#
# And also ensure it's not a newline right after sentence-ending punctuation.

# Strategy: Replace newline followed by a lowercase letter or space
# This is usually a good heuristic for mid-sentence breaks.
processed_content_2 = re.sub(r'(?<![.!?;:])\n(?![ \n\t\r])', ' ', book_content) # Newline not preceded by sentence end, and not followed by blank space/newline
processed_content_2 = re.sub(r'(\S)\s*\n([a-z])', r'\1 \2', processed_content_2) # Word \n lowercase letter -> Word lowercase letter
processed_content_2 = re.sub(r'\s{2,}', ' ', processed_content_2).strip() # Replace multiple spaces with single space

# A simpler, often effective regex:
# Replace a newline that is not followed by another newline AND is not preceded by sentence-ending punctuation.
# This pattern looks for a newline that is *not* part of a double newline AND is *not* immediately preceded by . ? ! ; :
processed_content_2_simpler = re.sub(r'(?<![.!?;:])\n(?![\n\r\t ])', ' ', book_content)
processed_content_2_simpler = re.sub(r'([a-zA-Z0-9])\n([a-zA-Z0-9])', r'\1 \2', processed_content_2_simpler) # Join word\nword
processed_content_2_simpler = re.sub(r'\s{2,}', ' ', processed_content_2_simpler).strip()


print("\n--- Approach 2 (Regex) ---")
print(processed_content_2_simpler)
