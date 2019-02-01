var exp_keywords = undefined;

var timeline_data = undefined;

var final_timeline_data = {};
var final_timeline_list = [];

function convert_timestamp(timestamp, precision='time') {
    // Precision: 'time' for HH:MM; 'date' for date only.
    var date_obj = new Date(timestamp);
    var year = date_obj.getFullYear().toString();
    var month = (date_obj.getMonth() + 1).toString().padStart(2, '0');
    var day = date_obj.getDate().toString().padStart(2, '0');
    var hour = date_obj.getHours().toString().padStart(2, '0');
    var minutes = date_obj.getMinutes().toString().padStart(2, '0');
    if(precision == 'time') {
        return (year + '-' + month + '-' + day + ' ' + hour + ':' + minutes);
    } else if(precision == 'shortened') {
        return (month + '/' + day + '/' + year.substring(2));
    }
    return (year + '-' + month + '-' + day);
}

function get_badge_accent(stories) {
    if(stories.length < 3) {
        return 'lighten-4'
    } else if(stories.length < 5) {
        return 'lighten-3'
    } else if(stories.length < 7) {
        return 'lighten-2'
    } else {
        return 'lighten-1'
    }
}

function update_progress(progress, empty=false) {
    // Updates progress modal
    var progress_template = Handlebars.compile($('#progress_item_template').html());
    var progress_item = progress_template(progress);
    if(empty) {
      $('#progress_text').empty();
    }
    $('#progress_text').append(progress_item);
}

function merge_clusters(ca, cb) {
    // Merges two clusters (used for drag-and-drop)
    var nc = Object.assign({}, cb);
    nc.stories = {...nc.stories, ...ca.stories};
    if(!cb.title_edited) {
        if(ca.title_edited) {
            nc.title = ca.title;
            nc.title_edited = ca.title_edited;
        }
    }
    if(ca.timestamp < cb.timestamp) {
        nc.timestamp = ca.timestamp
    }
    return nc;
}

function submit_query_keywords(ui_callback) {
    // Actions after user presses "search"
    var kw = $('#keywords-input').val();
    console.log(kw);
    if(kw.length == 0) {
        return;
    }
    update_progress({
        icon: 'access_time',
        text: 'Retrieving relevant keywords...'
    }, true)
    $('#progress').modal('open');
    $.ajax({
        url: 'query',
        type: 'POST',
        data: {
            keywords: kw,
        },
        dataType: 'json',
        success: function(result) {
            console.log(result);
            var kw_rows = '';
            for(var i = 0; i < result['exp_keywords'].length; i ++) {
                var new_row = ('Related to <div class="chip">' + result['exp_keywords'][i][0] + '</div>: ' );
                for(var j = 1; j < result['exp_keywords'][i].length; j ++) {
                    new_row += ('<div class="chip">' + result['exp_keywords'][i][j] + '<i class="close material-icons ph-kw-delete" forKeyword="' + result['exp_keywords'][i][j] + '"  keywordGroup="' + i.toString() + '">close</i></div>');
                }
                kw_rows += ('<p style="display:inline-block">' + new_row + '</p>');
            }
            exp_keywords = result['exp_keywords'];
            $('#div_exp_keywords').html(kw_rows);
            $('#progress').modal('close');
            $('.ph-kw-delete').click(function() {
                console.log(exp_keywords);
                console.log($(this).attr('forKeyword'));
                console.log($(this).attr('keywordGroup'));
                var rmIdx = exp_keywords[parseInt($(this).attr('keywordGroup'))].indexOf($(this).attr('forKeyword'));
                exp_keywords[parseInt($(this).attr('keywordGroup'))].splice(rmIdx, 1);
                console.log(exp_keywords);
            });
            if(ui_callback) {
                ui_callback();
            }
        }
    });
}

function submit_expanded_keywords(ui_callback) {
    // Actions after user presses "continue" in expanded keywords
    $('#progress').modal('open');
    update_progress({
        icon: 'access_time',
        text: 'Looking up stories...'
    }, true);
    $.ajax({
        url: 'lookup',
        type: 'POST',
        data: {
            keywords: exp_keywords,
        },
        dataType: 'json',
        success: function(result) {
            console.log(result);
            update_progress({
                icon: 'check',
                text: 'We found ' + result['num_stories'] + ' stories.'
            });
            update_progress({
                icon: 'access_time',
                text: 'Processing stories...'
            });
            request_processing(ui_callback);
        }
    });
}

function request_processing(ui_callback) {
    // Actions after the server completes the story query
    $.ajax({
        url: 'vectorize',
        type: 'POST',
        success: function(result) {
            console.log(result);
            update_progress({
                icon: 'check',
                text: 'Stories processed.'
            });
            update_progress({
                icon: 'access_time',
                text: 'Clustering stories...'
            });
            request_clustering(ui_callback);
        }
    });
}

function convert_to_display(cluster) {
    // Returns cluster with stories sorted by timestamp instead of as a dictionary
    var rcluster = Object.assign({}, cluster);
    delete rcluster.stories;
    var rcluster_stories = [];
    for(var skey in cluster.stories) {
        rcluster_stories.push(cluster.stories[skey]);
    }
    rcluster_stories.sort(function(item1, item2) {
        return item1.timestamp > item2.timestamp ? 1 : -1;
    });
    rcluster.stories = rcluster_stories;
    return rcluster;
}

function request_clustering(ui_callback) {
    // Actions after the server vectorizes stories
    $.ajax({
        url: 'cluster',
        type: 'POST',
        dataType: 'json',
        data: {
            par: 0.4
        },
        success: function(result) {
            console.log(result);
            timeline_data = {};
            for(var i = 0; i < result.length; i ++) {
                var new_key = 'cluster' + i.toString();
                timeline_data[new_key] = {
                    key: new_key,
                    timestamp: result[i][0],
                    title: result[i][1][0].title,
                    title_edited: false,
                    selected: true,
                    stories: {}
                };
                for(var j = 0; j < result[i][1].length; j ++) {
                    var story_key = new_key + 'story' + j;
                    timeline_data[new_key].stories[story_key] = Object.assign({}, {...result[i][1][j], key: story_key, selected: true});
                }
            }
            console.log(timeline_data);

            timeline_display_data = [];
            for(var key in timeline_data) {
                timeline_display_data.push(convert_to_display(timeline_data[key]));
            }

            var raw_timeline_template = Handlebars.compile($('#raw_timeline_template').html());
            $('#timeline_raw_content').html(raw_timeline_template({clusters: timeline_display_data}));

            var item_template = Handlebars.compile($('#raw_timeline_item').html());

            $('.event_checkbox').on('click', function(event) {
                var cluster_key = $(this).parent().attr('forCluster');
                timeline_data[cluster_key].selected = $(this).is(':checked');
                if(!$(this).is(':checked')) {
                    $('label.story_checkbox_wrapper[forCluster="' + cluster_key + '"]').find('input[type="checkbox"]').attr('disabled', 'disabled');
                } else {
                    $('label.story_checkbox_wrapper[forCluster="' + cluster_key + '"]').find('input[type="checkbox"]').removeAttr('disabled');
                }
            });

            $('.event_checkbox_wrapper').on('click', function(event) {
                event.stopPropagation();
            });

            $('.story_checkbox').on('click', function(event) {
                var cluster_key = $(this).parent().attr('forCluster');
                var story_key = $(this).parent().attr('forStory');
                timeline_data[cluster_key].stories[story_key].selected = $(this).is(':checked');
                event.stopPropagation();
            });

            var draggable_options = {
                revert: true,
                start: function(event, ui) {
                    $('#droppable_trash').fadeIn(100);
                },
                stop: function(event, ui) {$('#droppable_trash').fadeOut(100)},
                classes: {
                    'ui-draggable-dragging': 'draggable_cluster_dragging'
                },
                stack: 'body'
            };

            var droppable_options = {
                drop: function(event, ui) {
                    ui.draggable.remove();
                    var from_id = ui.draggable.attr('forCluster');
                    var to_id = $(this).attr('forCluster');
                    var new_cluster = merge_clusters(timeline_data[from_id], timeline_data[to_id]);
                    timeline_data[to_id] = new_cluster;
                    var new_element = $(item_template(convert_to_display(timeline_data[to_id])));
                    $(this).replaceWith(new_element);
                    new_element.draggable(draggable_options);
                    new_element.droppable(droppable_options);

                    new_element.find('.event_checkbox').on('click', function(event) {
                        var cluster_key = $(this).parent().attr('forCluster');
                        timeline_data[cluster_key].selected = $(this).is(':checked');
                        if(!$(this).is(':checked')) {
                            $('label.story_checkbox_wrapper[forCluster="' + cluster_key + '"]').find('input[type="checkbox"]').attr('disabled', 'disabled');
                        } else {
                            $('label.story_checkbox_wrapper[forCluster="' + cluster_key + '"]').find('input[type="checkbox"]').removeAttr('disabled');
                        }
                    });

                    new_element.find('.event_checkbox_wrapper').on('click', function(event) {
                        event.stopPropagation();
                    });

                    new_element.find('.story_checkbox').on('click', function(event) {
                        var cluster_key = $(this).parent().attr('forCluster');
                        var story_key = $(this).parent().attr('forStory');
                        timeline_data[cluster_key].stories[story_key].selected = $(this).is(':checked');
                        event.stopPropagation();
                    });
                }
            }

            $('.timeline_raw_li').draggable(draggable_options);

            $('.timeline_raw_li').droppable(droppable_options);

            $('input.cluster_title').keyup(function() {
                var cluster_key = $(this).parent().attr('forCluster');
                $('span.raw_timeline_title[forCluster="' + cluster_key + '"]').html($(this).val());
                timeline_data[cluster_key].title = $(this).val();
                timeline_data[cluster_key].title_edited = true;
            });

            $('.collapsible').collapsible();
            $('#timeline-raw').show();
            $('#progess_text').empty();
            $('#progress').modal('close');

            /*
            $('html, body').animate({
                scrollTop: $('#timeline_raw').offset().top
            }, 500);
            */
            if(ui_callback) {
                ui_callback();
            }
        }
    });
}

function show_timeline(ui_callback) {
    final_timeline_data = {};

    for(var key in timeline_data) {
        if(timeline_data[key].selected) {
            final_timeline_data[key] = Object.assign({}, timeline_data[key]);
            var cluster_stories = [];
            for(var skey in final_timeline_data[key].stories) {
                if(final_timeline_data[key].stories[skey].selected) {
                    cluster_stories.push(final_timeline_data[key].stories[skey]);
                }
            }
            cluster_stories.sort(function(item1, item2) {
                return item1.timestamp > item2.timestamp ? 1 : -1;
            });
            final_timeline_data[key].stories = cluster_stories;
            if(!final_timeline_data[key].title_edited) {
                final_timeline_data[key].title = cluster_stories[0].title;
            }
            final_timeline_data[key].timestamp = cluster_stories[0].timestamp;
        }
    }

    console.log(final_timeline_data);

    //final_timeline_data = Object.assign({}, timeline_data);

    final_timeline_list.length = 0;
    for(var key in final_timeline_data) {
        final_timeline_list.push(final_timeline_data[key]);
    }
    final_timeline_list.sort(function(item1, item2) {
        return item1.timestamp > item2.timestamp ? 1 : -1;
    });

    var timeline_container_source = document.getElementById('timeline_accordion_template');
    var timeline_container_template = Handlebars.compile(timeline_container_source.innerHTML);
    $('#timeline_container').html(timeline_container_template({clusters: final_timeline_list}));

    var template_source = document.getElementById('timeline_item_template').innerHTML;
    var template = Handlebars.compile(template_source);

    var timeline_options = {
        template: template,
    };

    var vis_timelines = {};
    var vis_datasets = {};

    for(var idx in final_timeline_list) {
        vis_datasets[final_timeline_list[idx].key] = new vis.DataSet(final_timeline_list[idx].stories.map(function(item) {
            return {
                id: item.key,
                start: new Date(item.timestamp),
                timestamp: item.timestamp,
                title: item.title,
                content: item.title,
                link: item.link,
                feedname: item.feedname
            }
        }));
    }

    $('.timeline_accordion').accordion({
        animate: 200,
        active: false,
        collapsible: true,
        heightStyle: "content",
        beforeActivate: function(event, ui) {
            var cluster_key = ui.newHeader.attr('forCluster');
            console.log(cluster_key);
            var timeline_container = ui.newPanel.find('.timeline_div')[0];
            if(timeline_container && (!(cluster_key in vis_timelines))) {
                vis_timelines[cluster_key] = new vis.Timeline(timeline_container, vis_datasets[cluster_key], timeline_options);
            }
        }
    });

    if(ui_callback) {
        ui_callback();
    }
}

function export_graphics(export_editor) {
    var generation_template = Handlebars.compile(document.getElementById('timeline_generation_template').innerHTML);

    var generation_tag = ('<script>' + generation_template({
        final_timeline_list: JSON.stringify(final_timeline_list, null, '\t')
    }) + '<\/script>');

    var container_template = ('<script id="timeline_accordion_template" type="text/x-handlebars-template">' + $('#timeline_accordion_template').html() + '<\/script>');

    var item_template = ('<script id="timeline_item_template" type="text/x-handlebars-template">' +  document.getElementById('timeline_item_template').innerHTML + '<\/script>');

    var jquery_js = '<script src="https:\/\/code.jquery.com\/jquery-3.3.1.min.js"><\/script>';

    var jquery_ui_js = '<script src="https:\/\/code.jquery.com\/ui\/1.12.1\/jquery-ui.min.js"><\/script>'

    var jquery_ui_css = '<link rel="stylesheet" href="https:\/\/code.jquery.com\/ui\/1.12.1\/themes\/base\/jquery-ui.css">'

    var handlebars_js = '<script src="https:\/\/cdnjs.cloudflare.com\/ajax\/libs\/handlebars.js\/4.0.11\/handlebars.js"><\/script>'

    var visjs_js = '<script src="https:\/\/cdnjs.cloudflare.com\/ajax\/libs\/vis\/4.21.0\/vis.js"><\/script>';
    var visjs_css = '<link rel="stylesheet" href="https:\/\/cdnjs.cloudflare.com\/ajax\/libs\/vis\/4.21.0\/vis-timeline-graph2d.min.css" \/>';

    var code_template = Handlebars.compile(document.getElementById('timeline_export_template').innerHTML);
    var code = code_template({
        jquery_js: jquery_js,
        jquery_ui_js: jquery_ui_js,
        jquery_ui_css: jquery_ui_css,
        handlebars_js: handlebars_js,
        visjs_js: visjs_js,
        visjs_css: visjs_css,
        container_template: container_template,
        item_template: item_template,
        generation_script: generation_tag
    });

    //console.log(code);

    export_editor.setValue(code);
    $('#export').modal('open');
}

function export_excel(data) {
    var workbook = new ExcelJS.Workbook();
    for(var ckey in data) {
        var new_sheet = workbook.addWorksheet(data[ckey].title.replace(/[^\w\s]/gi, ''));
        new_sheet.columns = [
            {header: 'Title', key: 'title'},
            {header: 'Time', key: 'time'},
            {header: 'Publication', key: 'feedname'},
            {header: 'Link', key: 'link'}
        ];
        for(var skey in data[ckey].stories) {
            var new_row = data[ckey].stories[skey];
            new_row.time = new Date(data[ckey].stories[skey].timestamp);
            new_sheet.addRow(new_row);
        }
    }
    workbook.xlsx.writeBuffer({
        base64: true
    }).then(function(xls64) {
        var a = document.createElement('a');
        var data = new Blob([xls64], {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
        var url = URL.createObjectURL(data);
        a.href = url;
        a.download = 'timeline.xlsx';
        document.body.appendChild(a);
        a.click();
        setTimeout(function() {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }, 20);
    })
}

function ui_show_expanded_keywords() {
    // Show the expanded keywords card and fade it in.
    $('#card-exp-keywords').show();
    $('#card-exp-keywords').toggleClass('ph-pre-fadein', false);
    // Remove the fade in class as it's no longer useful.
    setTimeout(function() {
        $('#card-exp-keywords').toggleClass('ph-fadein', false);
    }, 1000);
}

function ui_show_raw_timeline() {
    // Shift the keywords cards to a column on the left.
    $('#col-keywords').toggleClass('m10 offset-m1 l8 offset-l2', false);
    $('#col-keywords').toggleClass('m4 l4', true);
    // Show the column for the raw timeline and fade it in.
    $('#col-timeline-raw').show();
    $('#col-timeline-raw').toggleClass('ph-pre-fadein', false);
    // Remove the fadein class as it is no longer useful.
    setTimeout(function() {
        $('#col-timeline-raw').toggleClass('ph-fadein', false);
        $('#col-timeline-raw').toggleClass('ph-slide', true);
    }, 1000);
}

function ui_show_final_timeline() {
    // Hide the keywords columns.
    $('#col-keywords').toggleClass('ph-fadein', true);
    $('#col-keywords').toggleClass('ph-pre-fadein', true);
    $('#col-keywords').hide();
    // Shift the column for the raw timeline to the left.
    $('#col-timeline-raw').toggleClass('m8 l8', false);
    $('#col-timeline-raw').toggleClass('m6 l5', true);
    // Fade the final timeline column in.
    $('#col-timeline-final').show();
    $('#col-timeline-final').toggleClass('ph-pre-fadein', false);
}

$(document).ready(function() {
    $('.modal').modal({
        dismissible: false
    });

    var export_editor = ace.edit('export_editor');
    export_editor.setTheme('ace/theme/monokai');
    export_editor.session.setMode('ace/mode/html');

    Handlebars.registerHelper('convert_timestamp_date', function(timestamp) {
        return convert_timestamp(timestamp, 'shortened');
    });

    Handlebars.registerHelper('convert_timestamp', function(timestamp) {
        return convert_timestamp(timestamp, 'time');
    });

    Handlebars.registerHelper('numkeys', function(obj) {
        return Object.keys(obj).length;
    });

    Handlebars.registerHelper('get_badge_accent', function(stories) {
        return get_badge_accent(stories);
    });

    Handlebars.registerPartial('item_partial', $('#raw_timeline_item').html());

    $('#submit_keywords').click(function() {
        console.log('clicked');
        submit_query_keywords(ui_show_expanded_keywords);
    });

    $('#keywords-input').keydown(function(event) {
        if($(this).val().length > 0) {
            $('#submit_keywords').removeClass('disabled');
        }
        if(event.which == 13) {
            submit_query_keywords(ui_show_expanded_keywords);
        }
    });

    $('#submit_new_kw').click(function(event) {
        event.preventDefault();
        console.log(exp_keywords);
        submit_expanded_keywords(ui_show_raw_timeline);
    });

    $('#submit_timeline').click(function(event) {
        event.preventDefault();
        show_timeline(ui_show_final_timeline);
    });

    M.Tooltip.init($('#export_json')[0], {
        enterDelay: 100,
        html: 'You can use the JSON format in your own visualization.',
        position: 'top'
    });

    M.Tooltip.init($('#export_excel')[0], {
        enterDelay: 100,
        html: '<span>You can export the excel visualization for easy viewing.</span><br /><span>Each event will be in its own worksheet.</span>',
        position: 'top'
    });

    M.Tooltip.init($('#export_timeline')[0], {
        enterDelay: 100,
        html: 'Download the graphic as embeddable HTML code.',
        position: 'top'
    });

    $('#export_json').click(function(event) {
        event.preventDefault();
        var data_json = JSON.stringify(final_timeline_data, null, 4);
        var element = document.createElement('a');
        element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(data_json));
        element.setAttribute('download', 'timeline.txt');
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    });

    $('#export_excel').click(function(event) {
        event.preventDefault();
        export_excel(final_timeline_data);
    });

    $('#export_timeline').click(function(event) {
        event.preventDefault();
        export_graphics(export_editor);
    });

    $('#timeline_download').click(function() {
        var element = document.createElement('a');
        element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(export_editor.getValue()));
        element.setAttribute('download', 'timeline.html');
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    });
});
