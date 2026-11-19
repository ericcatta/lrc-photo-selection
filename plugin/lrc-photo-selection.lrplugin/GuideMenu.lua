local Context = import 'LrFunctionContext'
Context.postAsyncTaskWithContext('Guida selezione fotografie', function()
    require('Guide').show()
end)
