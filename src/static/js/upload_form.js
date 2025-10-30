document.addEventListener('DOMContentLoaded', () => {
    const uploadFolderBtn = document.getElementById('uploadFolderBtn');
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.webkitdirectory = true;
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    if (uploadFolderBtn) {
        uploadFolderBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }

    fileInput.addEventListener('change', async (event) => {
        try {
            const files = event.target.files;
            const fileData = [];
            for (const file of files) {
                const content = await file.text();
                fileData.push({
                    name: file.name,
                    content: content,
                    webkitRelativePath: file.webkitRelativePath
                });
            }

            const patternType = document.getElementById('pattern_type').value;
            const pattern = document.getElementById('pattern').value;
            const max_file_size = document.getElementById('file_size').value;

            const response = await fetch('/api/upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    files: fileData,
                    pattern_type: patternType,
                    pattern: pattern,
                    max_file_size: max_file_size,
                }),
            });

            const result = await response.json();
            handleUploadResponse(result);

        } catch (error) {
            console.error('Error processing directory:', error);
        }
    });

    function handleUploadResponse(result) {
        if (result.error) {
            const errorMessage = document.getElementById('error-message');
            errorMessage.textContent = result.error;
            errorMessage.classList.remove('hidden');
            return;
        }

        const resultContainer = document.getElementById('resultContainer');
        const summaryElement = resultContainer.querySelector('#summary');
        const treeElement = resultContainer.querySelector('#tree');
        const contentElement = resultContainer.querySelector('#content');
        const shortRepoUrlElement = resultContainer.querySelector('#short_repo_url');

        summaryElement.textContent = result.summary;
        treeElement.textContent = result.tree;
        contentElement.textContent = result.content;
        shortRepoUrlElement.textContent = result.short_repo_url;
        resultContainer.classList.remove('hidden');
    }
});
