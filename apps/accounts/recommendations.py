from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from apps.jobs.models import Job  # Adjust this if your Job model path is different

def get_job_recommendations(seeker_profile, all_jobs):
    """
    Compares seeker's profile text against all active jobs.
    Returns a list of jobs sorted by similarity score.
    """
    if not all_jobs:
        return []

    # 1. Prepare the text data
    # We combine title, description, and requirements for a better match
    job_texts = [f"{job.title} {job.description} {job.requirements}" for job in all_jobs]
    
    # 2. Add the seeker's profile (skills + experience) to the end of the list
    all_texts = job_texts + [seeker_profile]
    
    # 3. Initialize TF-IDF Vectorizer
    # 'english' stop words removes common words like 'the', 'is', 'at'
    tfidf = TfidfVectorizer(stop_words='english')
    
    try:
        tfidf_matrix = tfidf.fit_transform(all_texts)
        
        # 4. Calculate Cosine Similarity
        # matrix[-1] is the seeker's profile. matrix[:-1] are all the jobs.
        cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
        
        # 5. Create a list of (job, score) tuples
        results = []
        scores = cosine_sim[0]
        for i, score in enumerate(scores):
            if score > 0:  # Only include if there is at least some match
                results.append({
                    'job': all_jobs[i],
                    'score': round(score * 100, 1)  # Convert to percentage
                })
        
        # 6. Sort by score in descending order
        return sorted(results, key=lambda x: x['score'], reverse=True)
        
    except Exception as e:
        print(f"AI Error: {e}")
        return []