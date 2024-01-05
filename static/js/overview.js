document.addEventListener("DOMContentLoaded", function() {
    var microblogTab = document.getElementById('microblog-tab');
    var blogTab = document.getElementById('blog-tab');
    
    var microblog = document.getElementById('microblog');
    var blog = document.getElementById('blog');

    var toggle = function() {
        microblogTab.classList.toggle('selected');
        microblog.classList.toggle('u-none');
        blogTab.classList.toggle('selected');
        blog.classList.toggle('u-none');
    };

    microblogTab.addEventListener('click', toggle);
    blogTab.addEventListener('click', toggle);
});
