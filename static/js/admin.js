dwell = {};
dwell.admin = {};
dwell.admin.kinds = {};

/* utility functions */
dwell.admin.openPublishForm = function(kind_id) {
  let btns = Array.from(document.getElementsByClassName('kind-select'));
  let frms = Array.from(document.getElementsByClassName('kind-form'));
  
  btns.forEach(element => {
    if (element.id == 'kind-' + kind_id) {
      element.classList.add('outline');
      element.classList.add('btn-primary');
    } else {
      element.classList.remove('outline');
      element.classList.remove('btn-primary');
    }
  });

  frms.forEach(element => {
    if (element.id == kind_id) {
      element.classList.remove('u-none');
    } else {
      element.classList.add('u-none');
    }
  });
};

dwell.admin.closePublishForm = function(kind_id) {
  let frm = document.getElementById(kind_id);
  let btn = document.getElementById('kind-' + kind_id);

  btn.classList.toggle('outline');
  btn.classList.toggle('btn-primary');
  frm.classList.toggle('u-none');
};

dwell.admin.publish = async function(kind) {
  let payload = dwell.admin.kinds[kind].payload(); 

  const response = await fetch("/micropub", {
    method: "POST",
    headers: {
      'Content-Type': 'application/json; charset=UTF-8'
    },
    body: JSON.stringify(payload)
  });
  
  if (response.ok) {
    window.location.href = response.headers.get('location');
  } else {
    dwell.notifications.notify('Error publishing post');
  }
};

dwell.admin.deletePost = async function(url) {
  const response = await fetch("/micropub", {
    method: "POST",
    headers: {
      'Content-Type': 'application/json; charset=UTF-8'
    },
    body: JSON.stringify({
      action: 'delete',
      url: url
    })
  });
  
  if (response.ok) {
    window.location.href = '/'; 
  } else {
    dwell.notifications.notify('Error deleting post');
  }
};

/* Notifications */
dwell.notifications = {
  SUCCESS: 'success',
  WARN: 'warning',
  ERROR: 'error',
  INFO: 'info',
  LINK: 'link',
  PRIMARY: 'primary',
  DARK: 'dark',
  GRAY: 'gray',

  notify: function(message, cls) {
    let notice = document.createElement('div');
    notice.classList.add('toast');
    notice.classList.add('toast--' + cls);
    notice.classList.add('animated');
    notice.classList.add('bounceIn');
    notice.style.position = 'fixed';
    notice.style.top = '50%';
    notice.style.left = '40%';
    notice.style.width = '20%';
    notice.style.zIndex = '10000000';
    
    let msg = document.createTextNode(message);
    notice.appendChild(msg);

    document.getElementsByTagName('main')[0].insertAdjacentElement('afterbegin', notice);
    
    setTimeout(function() {
      notice.remove();
    }, 3000);
  }
};

/* Kind: Review */
dwell.admin.kinds.review = {};

dwell.admin.kinds.review.setStarRating = function(rating) {
  document.getElementById('review-rating').value = rating;

  let btns = Array.from(document.getElementsByClassName('rating-choice'));

  btns.forEach(element => {
    if (parseInt(element.id.split('-')[1]) <= rating) {
      // these icons should be solid
      for (child of element.children) {
        if (child.classList.contains('rating-star-on')) {
          child.classList.remove('u-none');
        } else {
          child.classList.add('u-none');
        }
      }
    } else {
      // these icons should be outline
      for (child of element.children) {
        if (child.classList.contains('rating-star-on')) {
          child.classList.add('u-none');
        } else {
          child.classList.remove('u-none');
        }
      }
    }
  })
};

dwell.admin.kinds.review.payload = function() {
  let payload = {
    type: ['h-;entry'],
    properties: {
      'post-kind': ['Review'],
      name: [
        document.getElementById('review-name').value
      ],
      item: [{
        type: ["h-product"],
        properties: {
          photo: [],
          url: [document.getElementById('review-target').value],
          name: [document.getElementById('review-target-name').value]
        }
      }],
      rating: [
        document.getElementById('review-rating').value
      ],
      content: [{
        html: review_quill.getText() 
      }]
    }
  };

  return payload;
};

/* Kind: Recipe */
dwell.admin.kinds.recipe = {};

dwell.admin.kinds.recipe.addIngredient = function() {
  let parent = document.getElementById('ingredients');
  let qty = document.getElementById('ingredient-qty');
  let name = document.getElementById('ingredient-name');
  let ident = Math.ceil(Math.random()*1000000).toString();
  
  if (qty.value.length == 0 || name.value.length == 0) {
    dwell.notifications.notify(
      'All ingredients must have a quantity and name',
      dwell.notifications.WARNING
    );
    return;
  } 

  parent.innerHTML += [
    '<div id="ingredient-'+ ident + '" class="form-group min-w-100p recipe-ingredient">',
    '  <input type="text" class="form-group-input w-20p recipe-ingredient-qty" value="' + qty.value + '"/>',
    '  <input type="text" class="form-group-input recipe-ingredient-name" value="'+ name.value + '"/>',
    '  <button class="form-group-btn btn-primary level-item" onclick="dwell.admin.kinds.recipe.removeIngredient(\'' + ident + '\')">',
    '    <ion-icon name="remove-circle" class="mt-1 text-xl"></ion-icon>',
    '  </button>',
    '</div>'
  ].join('');

  qty.value = '';
  name.value = '';
};

dwell.admin.kinds.recipe.removeIngredient = function(ident) {
  let parent = document.getElementById('ingredient-' + ident);
  parent.remove();
};

dwell.admin.kinds.recipe.payload = function() {
  let payload = {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Recipe'],
      name: [
        document.getElementById('recipe-name').value
      ] 
    },
    children: [{
      type: [
        'h-recipe'
      ],
      properties: {
        name: [document.getElementById('recipe-name').value],
        ingredient: [],
        duration: [document.getElementById('recipe-duration').value],
        yield: [document.getElementById('recipe-yield').value],
        instructions: [{
          'html': recipe_quill.getText() 
        }]
      }
    }]
  };
  
  let els = Array.from(document.getElementsByClassName('recipe-ingredient'));
  els.forEach(element => {
    let qty = element.getElementsByClassName(
      'recipe-ingredient-qty'
    )[0].value;
    
    let name = element.getElementsByClassName(
      'recipe-ingredient-name'
    )[0].value;
  
    payload['children'][0]['properties']['ingredient'].push(qty + ' ' + name);
  });

  return payload;
};

/* Kind: Entry */
dwell.admin.kinds.entry = {};

dwell.admin.kinds.entry.payload = function() {
  return {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Entry'],
      name: [
        document.getElementById('entry-name').value
      ], 
      content: [{
        'html': entry_quill.getText()
      }]
    }
  }
};

/* Kind: Like */
dwell.admin.kinds.like = {};

dwell.admin.kinds.like.setInteractionType = function(interaction) {
  document.getElementById('like-interaction').value = interaction;
  document.getElementById('like-btn-like').classList.remove('btn-primary');
  document.getElementById('like-btn-repost').classList.remove('btn-primary');
  document.getElementById('like-btn-bookmark').classList.remove('btn-primary');
  document.getElementById('like-btn-' + interaction).classList.add('btn-primary');
};

dwell.admin.kinds.like.payload = function() { 
  let payload = {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Like'],
      name: [
        document.getElementById('like-name').value
      ], 
      content: [{
        'html': like_quill.getText() 
      }]
    }
  };
  
  let interaction = document.getElementById('like-interaction').value;
  payload['properties'][interaction + '-of'] = [
    document.getElementById('like-target').value
  ];

  return payload;
};

/* Kind: Status */
dwell.admin.kinds.status = {};

dwell.admin.kinds.status.payload = function() {
  return {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Status'],
      name: [
        document.getElementById('status-name').value
      ], 
      content: [{
        'html': document.getElementById('status-name').value
      }]
    }
  }
};

/* Kind: Reply */
dwell.admin.kinds.reply = {};

dwell.admin.kinds.reply.payload = function() {
  return {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Reply'],
      name: [
        document.getElementById('reply-name').value
      ], 
      content: [{
        'html': document.getElementById('reply-name').value
      }],
      'in-reply-to': [
        document.getElementById('reply-target').value
      ]
    }
  };
};

/* Kind: Listen */
dwell.admin.kinds.listen = {};

dwell.admin.kinds.listen.payload = function() {
  return {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Listen'],
    },
    children: [{
      type: ['h-cite'],
      properties: {
        name: [
          'Listened to ' + document.getElementById('listen-target-name').value
        ],
        'listen-of': [
          document.getElementById('listen-target').value
        ],
        photo: [],
        content: [{
          html: listen_quill.getText() 
        }]
      }
    }]
  };
};

/* Kind: Photo */
dwell.admin.kinds.photo = {};

dwell.admin.kinds.photo.payload = function() {
  let payload = {
    type: ['h-entry'],
    properties: {
      'post-kind': ['Photo'],
      name: [document.getElementById('photo-name').value]
    }
  }
  
  let content = photo_quill.getText(); 
  // TODO: inject photo references
  
  payload.properties.content = [{html: content}];

  return payload;
};
