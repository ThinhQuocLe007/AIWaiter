from langchain_huggingface import HuggingFaceEmbeddings

def get_embedding_model(): 
    return HuggingFaceEmbeddings(
        model_name='AITeamVN/Vietnamese_Embedding'
    )
